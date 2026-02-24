"""채팅 서비스

채팅방 관리 및 메시지 관련 비즈니스 로직
"""
# KoBART에서 생성한 Gloss Token 전처리 후 DB Word-Video url 연결을 위해 추가 (소영)
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text
# 추가 (소영)
from sqlalchemy import bindparam
from fastapi import HTTPException

# KoBART에서 생성한 Gloss Token 전처리 후 DB Word-Video url 연결을 위해 추가 (소영)
from app.services.model_client import ModelClient
from app.services.text_preprocessor import normalize_input_text
from app.services.gloss_preprocessor import clean_gloss
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

class ChatService:
    """채팅 관련 비즈니스 로직 처리"""

    # KoBART에서 생성한 Gloss Token 전처리 후 DB Word-Video url 연결을 위해 추가 (소영)
    @staticmethod
    def gloss_to_urls(gloss: str) -> tuple[list[str], list[str]]:
        """
        cleaned gloss -> corpus 테이블을 조회하여 url_path 리스트를 만든다.
        - 시간 토큰(f:1 등)은 매핑 제외(보존은 gloss 문자열에서만)
        - 매핑 실패 토큰은 miss로 반환
        """
        if not isinstance(gloss, str) or not gloss.strip():
            return [], []

        # 여기서 clean_gloss를 먼저 적용 (매핑률/미스 일관성 확보)
        gloss_clean = clean_gloss(gloss)
        if not gloss_clean:
            return [], []

        tokens = [t for t in gloss_clean.split() if t and not t.startswith("f:")]
        if not tokens:
            return [], []

        # DB 조회는 중복 제거해서 효율화
        unique_tokens = list(dict.fromkeys(tokens))

        db = SessionLocal()
        try:
            rows = db.execute(
                text("""
                    SELECT word_name, url_path
                    FROM multicampus_schema.corpus
                    WHERE word_name IN :tokens
                """).bindparams(bindparam("tokens", expanding=True)),
                {"tokens": unique_tokens}
            ).fetchall()

            mapping = {r[0]: r[1] for r in rows if r and r[0] and r[1]}

            urls: list[str] = [mapping[t] for t in tokens if t in mapping]
            miss = [t for t in tokens if t not in mapping]

            if miss:
                logger.debug("[URL MAP] miss_sample=%s total=%d", miss[:10], len(miss))
            return urls, miss

        finally:
            db.close()


    @staticmethod
    def text_to_gloss_and_urls_sync(text: str) -> Dict[str, Any]:
        """
        (동기) 텍스트를 모델서버에 보내 gloss를 받고, URL 리스트까지 반환한다.
        socekets.py에서 run_in_threadpool로 호출하기 위한 형태. 
        """
        client = ModelClient()
        # fastText는 보조 단계이므로 WS 지연 방지를 위해 짧은 timeout 사용
        fasttext_client = ModelClient(timeout_sec=2.0)
        clean_text = normalize_input_text(text)

        # 모델 입력은 normalize_input_text까지만 적용한 텍스트를 그대로 사용
        # (문장 분리/점 제거/하드컷 금지)
        # [v1 호환] 모델 입력 전용: 문장부호를 공백으로 치환 + 공백 정규화
        model_text = (
            clean_text
            .replace(".", " ")
            .replace("?", " ")
            .replace("!", " ")
        )
        model_text = " ".join(model_text.split())

        logger.info("[CHAT] start raw_len=%d model_len=%d", len(text), len(model_text))

        # 멀티 model_server 표준 호출로 전환
        t_kobart = time.time()
        # [v1 동치화 시도] generation 파라미터를 payload로 고정해서 경로 차이 축소
        infer_res = client.infer_sync(
            "kobart",
            model_text,
            payload={"top_k": 1, "max_new_tokens": 64, "num_beams": 4}
        )
        logger.info("[TIMING] kobart_ms=%d", int((time.time() - t_kobart) * 1000))

        # 지금은 infer 표준 응답(ok/task/result) 흐름으로 통일
        result = infer_res.get("result") if isinstance(infer_res, dict) else None
        gloss: Optional[str] = result.get("gloss") if isinstance(result, dict) else None
        meta = result.get("meta") if isinstance(result, dict) and isinstance(result.get("meta"), dict) else None
        
        # [DEBUG] /infer/kobart 경로 메타 확인 (device/params/model_dir/model_text)
        logger.debug("[KOBART META] %s", meta)
        logger.debug("[KOBART GLOSS RAW FULL_PREVIEW] %r", (gloss or "")[:300])

        # 모델 응답 gloss 후처리 (토큰 정제)
        if not gloss:
            return {"gloss": None, "urls": [], "miss": [], "meta": meta}

        t_map = time.time()
        gloss_clean = clean_gloss(gloss)
        urls, miss = ChatService.gloss_to_urls(gloss_clean)
        logger.info("[TIMING] url_map_ms=%d", int((time.time() - t_map) * 1000))

        # Step A: miss 토큰이 있을 때만 fastText 호출 (실패해도 절대 전체 흐름 실패시키지 않음)
        if miss:
            trace_id = f"ft-{len(miss)}"
            try:
                t_ft = time.time()
                fast_res = fasttext_client.infer_payload_sync("fasttext", {"tokens": miss})
                logger.info("[TIMING] fasttext_ms=%d", int((time.time() - t_ft) * 1000))
                logger.debug(
                    "[FASTTEXT][%s] miss_cnt=%d resp_preview=%r",
                    trace_id,
                    len(miss),
                    str(fast_res)[:400],
                )
            except Exception as e:
                # Step A에서는 fastText 실패를 무조건 삼키고 진행 (스택트레이스는 남기지 않음)
                logger.warning("[FASTTEXT][%s] call failed (Step A): %s", trace_id, e)
                fast_res = {"ok": False, "task": "fasttext", "error": "timeout", "result": None}
        else:
            logger.debug("[FASTTEXT] skip (no miss tokens)")

        logger.info(
            "[CHAT] done gloss_len=%d url_cnt=%d miss_cnt=%d",
            len(gloss_clean) if gloss_clean else 0,
            len(urls),
            len(miss)
        )

        # Step A에서는 절대 merge 하지 않고 기존 결과 그대로 반환
        return {"gloss": gloss_clean, "urls": urls, "miss": miss, "meta": meta}

    @staticmethod
    def search_users(db: Session, my_id: str, name: str = None, member_id: str = None):
        """사용자 검색
        
        이름 또는 아이디로 검색 (본인 제외)
        
        Returns:
            list: [{"member_no", "member_id", "user_name"}, ...]
        """
        if not name and not member_id:
            return []
        
        query_str = """
            SELECT member_no, member_id, full_name 
            FROM multicampus_schema.member
            WHERE member_id != :my_id
        """
        params = {"my_id": my_id}
        
        if name:
            query_str += " AND full_name LIKE :name"
            params["name"] = f"%{name}%"
        
        if member_id:
            query_str += " AND member_id LIKE :member_id"
            params["member_id"] = f"%{member_id}%"
            
        results = db.execute(text(query_str), params).fetchall()
        
        return [
            {"member_no": row[0], "member_id": row[1], "user_name": row[2]} 
            for row in results
        ]

    @staticmethod
    def create_or_get_room(db: Session, my_id: str, target_id: str):
        """채팅방 생성 또는 조회
        
        두 사용자 간 1:1 채팅방 조회/생성
        
        Returns:
            dict: {"room_id": int, "message": str}
        """
        # 회원 번호 조회
        get_no_sql = text("SELECT member_no FROM multicampus_schema.member WHERE member_id = :id")
        my_no = db.execute(get_no_sql, {"id": my_id}).scalar()
        target_no = db.execute(get_no_sql, {"id": target_id}).scalar()
        
        if not my_no or not target_no:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # 기존 방 확인
        check_room_sql = text("""
            SELECT talk_room_id FROM multicampus_schema.talk_room
            WHERE (member_no1 = :m1 AND member_no2 = :m2)
               OR (member_no1 = :m2 AND member_no2 = :m1)
        """)
        room_id = db.execute(check_room_sql, {"m1": my_no, "m2": target_no}).scalar()

        if room_id:
            return {"room_id": room_id, "message": "이미 존재하는 채팅방입니다."}

        # 새 방 생성
        create_room_sql = text("""
            INSERT INTO multicampus_schema.talk_room (
                talk_room_id, member_no1, member_no2, create_user
            ) VALUES (
                nextval('multicampus_schema.talk_room_id_s'), :m1, :m2, :creator
            ) RETURNING talk_room_id
        """)
        
        try:
            new_room_id = db.execute(create_room_sql, {
                "m1": my_no, "m2": target_no, "creator": my_id
            }).scalar()
            
            db.commit()
            return {"room_id": new_room_id, "message": "새 채팅방 생성 완료"}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="채팅방 생성 실패")

    @staticmethod
    def get_my_rooms(db: Session, user_id: str):
        """내 채팅방 목록 조회
        
        Returns:
            list: [{"user_id", "user_name"}, ...]
        """
        # 내 회원 번호 조회
        my_no_sql = text("SELECT member_no FROM multicampus_schema.member WHERE member_id = :id")
        my_no = db.execute(my_no_sql, {"id": user_id}).scalar()

        # 채팅 목록 조회 (UNION으로 member_no1, member_no2 양쪽 처리)
        chat_list_sql = text("""
            SELECT A1.member_no1 AS member_no,
                   (SELECT CC1.member_id FROM multicampus_schema.member CC1 WHERE A1.member_no1 = CC1.member_no) AS member_id,
                   (SELECT CC1.full_name FROM multicampus_schema.member CC1 WHERE A1.member_no1 = CC1.member_no) AS full_name
            FROM (
                SELECT BB1.member_no1, BB1.member_no2
                FROM multicampus_schema.member AA1, multicampus_schema.talk_room BB1
                WHERE AA1.member_no = :my_no 
                  AND (AA1.member_no = BB1.member_no1 OR AA1.member_no = BB1.member_no2)
            ) A1
            WHERE A1.member_no1 != :my_no
            UNION
            SELECT A2.member_no2 AS member_no,
                   (SELECT CC2.member_id FROM multicampus_schema.member CC2 WHERE A2.member_no2 = CC2.member_no) AS member_id,
                   (SELECT CC2.full_name FROM multicampus_schema.member CC2 WHERE A2.member_no2 = CC2.member_no) AS full_name
            FROM (
                SELECT BB2.member_no1, BB2.member_no2
                FROM multicampus_schema.member AA2, multicampus_schema.talk_room BB2
                WHERE AA2.member_no = :my_no 
                  AND (AA2.member_no = BB2.member_no1 OR AA2.member_no = BB2.member_no2)
            ) A2
            WHERE A2.member_no2 != :my_no
        """)
        
        results = db.execute(chat_list_sql, {"my_no": my_no}).fetchall()
        
        return [
            {"user_id": row[1], "user_name": row[2]} 
            for row in results
        ]

    @staticmethod
    def get_chat_history(db: Session, room_id: int):
        """채팅방 대화 내역 조회
        
        Returns:
            list: [{"message", "sender", "sender_name", "date"}, ...]
        """
        # 영상 히스토리 저장을 위해 수정합니다. (소영)
        history_sql = text("""
            SELECT
                T.message,
                M.member_id,
                M.full_name,
                T.talk_date,
                (
                    SELECT ARRAY_AGG(BB.url_path ORDER BY BB.seq)
                    FROM multicampus_schema.talk_detail BB
                    WHERE BB.talk_room_id = T.talk_room_id
                    AND BB.member_no = T.member_no
                    AND BB.talk_date = T.talk_date
                ) AS urls
            FROM multicampus_schema.talk T
            JOIN multicampus_schema.member M ON T.member_no = M.member_no
            WHERE T.talk_room_id = :r_id
            ORDER BY T.talk_date ASC
        """)
        
        results = db.execute(history_sql, {"r_id": room_id}).fetchall()
        
        return [
            {
                "message": row[0], 
                "sender": row[1],
                "sender_name": row[2],
                "date": row[3].strftime("%H:%M"),
                "urls": row[4] or []
            } for row in results
        ]
