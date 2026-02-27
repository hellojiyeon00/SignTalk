"""채팅 서비스

채팅방 관리 및 메시지 관련 비즈니스 로직
"""
# KoBART에서 생성한 Gloss Token 전처리 후 DB Word-Video url 연결을 위해 추가
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from sqlalchemy import bindparam
from fastapi import HTTPException

# KoBART에서 생성한 Gloss Token 전처리 후 DB Word-Video url 연결을 위해 추가
from app.services.model_client import ModelClient
from app.services.text_preprocessor import normalize_input_text
from app.services.gloss_preprocessor import clean_gloss
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# 채팅 서비스 클래스 정의
class ChatService:
    """채팅 관련 비즈니스 로직 처리"""

    # ModelClient 재사용(keep-alive/pool 활용)
    # - kobart: 기본 timeout
    # - fasttext: timeout 5초로 완화(원인 분리 목적)
    _kobart_client = ModelClient()
    _fasttext_client = ModelClient(timeout_sec=5.0)

    @staticmethod
    def _apply_fasttext_best(
        gloss_clean: str,
        miss_tokens: list[str],
        fast_res: dict,
        threshold: float = 0.65,
    ) -> tuple[str, list[dict]]:
        """
        fastText best 결과를 gloss_clean에 '치환' 적용한다.

        규칙:
        - miss_tokens에 대해서만 적용
        - fast_res[token].best 가 존재하고 score >= threshold 인 경우에만 치환
        - 치환은 토큰 단위(공백 split) 기준으로 '동일 토큰'만 교체

        반환:
        - new_gloss: 치환된 gloss 문자열
        - replaced: 치환 내역 리스트 [{src, dst, score}]
        """
        if not gloss_clean or not miss_tokens or not fast_res:
            return gloss_clean, []

        tokens = [t for t in gloss_clean.split() if t.strip()]
        if not tokens:
            return gloss_clean, []

        miss_set = set(miss_tokens)
        replaced: list[dict] = []

        for i, tok in enumerate(tokens):
            if tok not in miss_set:
                continue

            info = fast_res.get(tok)
            if not isinstance(info, dict):
                continue

            best = info.get("best")
            score = info.get("score")

            if not best or not isinstance(best, str):
                continue
            try:
                score_f = float(score)
            except Exception:
                continue

            if score_f < threshold:
                continue

            if best == tok:
                continue

            tokens[i] = best
            replaced.append({"src": tok, "dst": best, "score": score_f})

        new_gloss = " ".join(tokens)
        return new_gloss, replaced


    # KoBART에서 생성한 Gloss Token 전처리 후 DB Word-Video url 연결을 위해 추가
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
        gloss_clean = gloss.strip()
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
        client = ChatService._kobart_client
        # fastText는 보조 단계이므로 WS 지연 방지를 위해 짧은 timeout 사용
        fasttext_client = ChatService._fasttext_client
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
        logger.info("[DEBUG GLOSS] raw=%r clean=%r", (gloss or "")[:200], (gloss_clean or "")[:200])
        urls, miss = ChatService.gloss_to_urls(gloss_clean)
        logger.info("[TIMING] url_map_ms=%d", int((time.time() - t_map) * 1000))

        # Step A: miss 토큰이 있을 때만 fastText 호출 (실패해도 절대 전체 흐름 실패시키지 않음)
        if miss:
            logger.info("[FASTTEXT] miss_tokens=%s", miss)
            trace_id = f"ft-{len(miss)}"
            try:
                t_ft = time.time()
                ft_payload = {"tokens": miss}
                logger.info("[FASTTEXT] send_payload=%s", ft_payload)

                fast_res = fasttext_client.infer_payload_sync("fasttext", ft_payload)
                
                logger.info("[FASTTEXT][%s] resp=%s", trace_id, str(fast_res)[:800])  # ✅ 추가 (INFO)
                logger.info("[TIMING] fasttext_ms=%d", int((time.time() - t_ft) * 1000))
                logger.debug(
                    "[FASTTEXT][%s] miss_cnt=%d resp_preview=%r",
                    trace_id,
                    len(miss),
                    str(fast_res)[:400],
                )
                # =========================
                # Step B: fastText best 적용 + 2차 URL 재매핑
                # =========================
                threshold = 0.65
                ft_results = {}

                if isinstance(fast_res, dict):
                    ft_result = fast_res.get("result") if isinstance(fast_res.get("result"), dict) else {}
                    ft_results = ft_result.get("results") if isinstance(ft_result.get("results"), dict) else {}

                    new_gloss, replaced = ChatService._apply_fasttext_best(
                        gloss_clean=gloss_clean,
                        miss_tokens=miss,
                        fast_res=ft_results,
                        threshold=threshold
                    )
                    
                    if replaced:
                        before_url_cnt = len(urls)
                        before_miss_cnt = len(miss)

                        logger.info("[FASTTEXT][%s] replaced=%s", trace_id, replaced)

                        # 2차 매핑
                        urls2, miss2 = ChatService.gloss_to_urls(new_gloss)

                        logger.info(
                            "[FASTTEXT][%s] remap url_cnt %d->%d miss_cnt %d->%d",
                            trace_id,
                            before_url_cnt,
                            len(urls2),
                            before_miss_cnt,
                            len(miss2),
                        )

                        # 최종 반영
                        gloss_clean = new_gloss
                        urls = urls2
                        miss = miss2
                    else:
                        logger.info("[FASTTEXT][%s] replaced=none", trace_id)
                else:
                    logger.info("[FASTTEXT][%s] skip(non-dict response)", trace_id)


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

        # Step B 적용 후 최종 결과 반환
        return {"gloss": gloss_clean, "urls": urls, "miss": miss, "meta": meta}

    # @staticmethod: 클래스 이름으로 직접 호출 가능한 정적 메서드 정의
    @staticmethod
    def search_users(db: Session, my_id: str, name: str = None, member_id: str = None):
        """사용자 검색
        
        이름 또는 아이디로 검색 (본인 제외)
        
        Returns:
            list: [{"member_no", "member_id", "user_name"}, ...]
        """
        # 검색 조건이 없으면 빈 리스트 반환 (과도한 DB 조회 방지)
        if not name and not member_id:
            return []
        
        # SQL: 본인 제외, 이름 또는 아이디로 검색
        query_str = """
            SELECT member_no, member_id, full_name 
            FROM multicampus_schema.member
            WHERE member_id != :my_id
        """
        params = {"my_id": my_id}
        
        # 이름/아이디 검색 조건 추가
        if name:
            query_str += " AND full_name LIKE :name"
            params["name"] = f"%{name}%"
        
        if member_id:
            query_str += " AND member_id LIKE :member_id"
            params["member_id"] = f"%{member_id}%"
        
        # SQL 실행 후 결과 반환  
        results = db.execute(text(query_str), params).fetchall()
        
        # 결과를 리스트로 변환하여 반환
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
        # 회원 번호 조회: my_id와 target_id로 member_no 조회
        # get_no_sql: member_id로 member_no 조회
        # my_no: 현재 사용자 번호, target_no: 상대방 사용자 번호
        get_no_sql = text("SELECT member_no FROM multicampus_schema.member WHERE member_id = :id")
        my_no = db.execute(get_no_sql, {"id": my_id}).scalar()
        target_no = db.execute(get_no_sql, {"id": target_id}).scalar()
        
        # 사용자 존재 여부 확인(둘 중 하나라도 없으면 404 에러)
        if not my_no or not target_no:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # SQL: 두 사용자 간 채팅방 존재 여부 확인 (member_no1, member_no2 양쪽 처리)
        check_room_sql = text("""
            SELECT talk_room_id FROM multicampus_schema.talk_room
            WHERE (member_no1 = :m1 AND member_no2 = :m2)
               OR (member_no1 = :m2 AND member_no2 = :m1)
        """)
        # room_id: 기존 채팅방 ID (존재하면 반환, 없으면 None)
        room_id = db.execute(check_room_sql, {"m1": my_no, "m2": target_no}).scalar()

        # 기존 방이 있으면 해당 방 ID와 메시지 반환
        if room_id:
            return {"room_id": room_id, "message": "이미 존재하는 채팅방입니다."}

        # SQL: 채팅방 생성 (talk_room_id는 시퀀스에서 자동 생성, create_user는 my_id)
        create_room_sql = text("""
            INSERT INTO multicampus_schema.talk_room (
                talk_room_id, member_no1, member_no2, create_user
            ) VALUES (
                nextval('multicampus_schema.talk_room_id_s'), :m1, :m2, :creator
            ) RETURNING talk_room_id
        """)
        
        try:
            # 채팅방 생성 후 새로 생성된 talk_room_id 반환
            new_room_id = db.execute(create_room_sql, {
                "m1": my_no, "m2": target_no, "creator": my_id
            }).scalar()
            db.commit()
            
            # 새 채팅방이 생성되었음을 알리는 메시지와 함께 방 ID 반환
            return {"room_id": new_room_id, "message": "새 채팅방 생성 완료"}
        except Exception as e:
            # DB 에러 발생 시 롤백하여 DB 상태 원복 (DB 꼬임 방지)
            db.rollback()
            raise HTTPException(status_code=500, detail="채팅방 생성 실패")

    @staticmethod
    def get_my_rooms(db: Session, user_id: str):
        """내 채팅방 목록 조회
        
        삭제되지 않은 친구만 표시 (delete_date IS NULL)
        읽지 않은 메시지 개수와 마지막 메시지 시간 포함
        
        Returns:
            list: [{"user_id", "user_name", "unread_count", "last_message_time"}, ...]
        """
        # 내 회원 번호 조회
        my_no_sql = text("SELECT member_no FROM multicampus_schema.member WHERE member_id = :id")
        my_no = db.execute(my_no_sql, {"id": user_id}).scalar()

        # SQL: 내 채팅방 목록 조회 + 읽지 않은 메시지 개수 + 마지막 메시지 시간
        chat_list_sql = text("""
            WITH chat_partners AS (
                SELECT A1.member_no1 AS member_no,
                       A1.talk_room_id
                FROM (
                    SELECT BB1.talk_room_id, BB1.member_no1, BB1.member_no2
                    FROM multicampus_schema.member AA1, multicampus_schema.talk_room BB1
                    WHERE AA1.member_no = :my_no 
                      AND (AA1.member_no = BB1.member_no1 OR AA1.member_no = BB1.member_no2)
                      AND BB1.delete_date IS NULL
                ) A1
                WHERE A1.member_no1 != :my_no
                UNION
                SELECT A2.member_no2 AS member_no,
                       A2.talk_room_id
                FROM (
                    SELECT BB2.talk_room_id, BB2.member_no1, BB2.member_no2
                    FROM multicampus_schema.member AA2, multicampus_schema.talk_room BB2
                    WHERE AA2.member_no = :my_no 
                      AND (AA2.member_no = BB2.member_no1 OR AA2.member_no = BB2.member_no2)
                      AND BB2.delete_date IS NULL
                ) A2
                WHERE A2.member_no2 != :my_no
            )
            SELECT 
                M.member_id,
                M.full_name,
                COALESCE(
                    (SELECT COUNT(*) 
                     FROM multicampus_schema.talk T
                     WHERE T.talk_room_id = CP.talk_room_id
                       AND T.member_no = CP.member_no
                       AND T.confirm_yn = 'N'), 
                    0
                ) AS unread_count,
                (SELECT MAX(T2.talk_date)
                 FROM multicampus_schema.talk T2
                 WHERE T2.talk_room_id = CP.talk_room_id) AS last_message_time
            FROM chat_partners CP
            JOIN multicampus_schema.member M ON CP.member_no = M.member_no
            ORDER BY last_message_time DESC NULLS LAST
        """)
        
        # SQL 실행 후 결과 반환
        results = db.execute(chat_list_sql, {"my_no": my_no}).fetchall()
        
        # 결과를 리스트로 변환하여 반환
        return [
            {
                "user_id": row[0], 
                "user_name": row[1],
                "unread_count": row[2],
                "last_message_time": row[3].isoformat() if row[3] else None
            } 
            for row in results
        ]

    @staticmethod
    def get_chat_history(db: Session, room_id: int, user_id: str):
        """채팅방 대화 내역 조회
        
        Args:
            room_id: 채팅방 ID
            user_id: 현재 사용자 ID (읽음 상태 판단용)
        
        Returns:
            list: [{"message", "sender", "sender_name", "date", "is_read"}, ...]
        """

        # SQL: 채팅방 대화 내역 조회 (confirm_yn 포함)
        history_sql = text("""
            SELECT T.message, M.member_id, M.full_name, T.talk_date, T.confirm_yn, COALESCE(D.urls, ARRAY[]::text[]) AS urls
            FROM multicampus_schema.talk T
            JOIN multicampus_schema.member M
            ON T.member_no = M.member_no
            LEFT JOIN (
                SELECT
                    talk_room_id,
                    member_no,
                    talk_date,
                    ARRAY_AGG(url_path ORDER BY word_order_no)
                    FILTER (WHERE url_path IS NOT NULL) AS urls
                FROM multicampus_schema.talk_detail
                GROUP BY talk_room_id, member_no, talk_date
            ) D
            ON D.talk_room_id = T.talk_room_id
            AND D.member_no    = T.member_no
            AND D.talk_date    = T.talk_date
            WHERE T.talk_room_id = :r_id
            ORDER BY T.talk_date ASC
        """)

        # SQL 실행 후 결과 반환
        results = db.execute(history_sql, {"r_id": room_id}).fetchall()
        
        # 결과를 리스트로 변환해 반환
        return [
            {
                "message": row[0], 
                "sender": row[1],
                "sender_name": row[2],
                "date": row[3].strftime("%H:%M"),
                "is_read": row[4] == 'Y',
                "urls": row[5] or []
            } for row in results
        ]
                # 모든 메시지는 confirm_yn으로 읽음 여부 판단
                # 'Y'이면 읽음, 'N'이면 읽지 않음

    @staticmethod
    def block_friend(db: Session, my_id: str, friend_id: str):
        """친구 삭제 (소프트 삭제)
        
        delete_user와 delete_date 컬럼을 업데이트하여 소프트 삭제 처리
        
        Returns:
            dict: {"message": str}
        """
        
        # 회원 번호 조회: my_id와 friend_id로 member_no 조회
        get_no_sql = text("SELECT member_no FROM multicampus_schema.member WHERE member_id = :id")
        my_no = db.execute(get_no_sql, {"id": my_id}).scalar()
        friend_no = db.execute(get_no_sql, {"id": friend_id}).scalar()
        
        # 사용자 존재 여부 확인(둘 중 하나라도 없으면 404 에러)
        if not my_no or not friend_no:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        # SQL: 친구 삭제 (delete_user와 delete_date 업데이트하여 소프트 삭제 처리, 양쪽 member_no 처리)
        delete_sql = text("""
            UPDATE multicampus_schema.talk_room
            SET delete_date = CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
                delete_user = :deleter
            WHERE ((member_no1 = :m1 AND member_no2 = :m2) 
                OR (member_no1 = :m2 AND member_no2 = :m1))
              AND delete_date IS NULL
        """)
        
        try:
            # SQL 실행 후 결과 반환 (실제 업데이트된 행 수로 성공 여부 판단)
            result = db.execute(delete_sql, {
                "m1": my_no, "m2": friend_no, "deleter": my_id
            })
            db.commit()
            
            # 업데이트된 행이 없으면(이미 삭제된 친구거나 존재하지 않는 친구) 404 에러 반환
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="차단할 친구를 찾을 수 없습니다.")
            
            return {"message": "친구가 차단되었습니다."}
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"친구 차단 실패: {str(e)}")

    @staticmethod
    def get_friend_list(db: Session, user_id: str):
        """친구 목록 조회 (설정 창용)
        
        모든 친구 표시 (차단된 친구 포함)
        
        Returns:
            list: [{"user_id", "user_name", "is_blocked"}, ...]
        """
        # 내 회원 번호 조회
        my_no_sql = text("SELECT member_no FROM multicampus_schema.member WHERE member_id = :id")
        my_no = db.execute(my_no_sql, {"id": user_id}).scalar()

        # SQL: 친구 목록 조회 (본인 제외, 차단 여부 포함, delete_date IS NULL인 친구는 is_blocked=False, delete_date NOT NULL인 친구는 is_blocked=True)
        friend_list_sql = text("""
            SELECT DISTINCT 
                M.member_id AS friend_id,
                M.full_name AS friend_name,
                CASE WHEN TR.delete_date IS NOT NULL THEN true ELSE false END AS is_blocked
            FROM multicampus_schema.talk_room TR
            JOIN multicampus_schema.member M ON (
                (TR.member_no1 = :my_no AND TR.member_no2 = M.member_no) OR
                (TR.member_no2 = :my_no AND TR.member_no1 = M.member_no)
            )
            WHERE (TR.member_no1 = :my_no OR TR.member_no2 = :my_no)
              AND M.member_no != :my_no
            ORDER BY is_blocked, M.full_name
        """)
        
        # SQL 실행 후 결과 반환
        results = db.execute(friend_list_sql, {"my_no": my_no}).fetchall()
        
        # 결과를 리스트로 변환하여 반환(row[0]: friend_id, row[1]: friend_name, row[2]: is_blocked)
        return [
            {
                "user_id": row[0],
                "user_name": row[1],
                "is_blocked": row[2]
            } for row in results
        ]

    @staticmethod
    def mark_messages_as_read(db: Session, room_id: int, user_id: str):
        """채팅방 메시지 읽음 처리
        
        특정 채팅방에서 상대방이 보낸 읽지 않은 메시지를 모두 읽음 처리
        
        Args:
            room_id: 채팅방 ID
            user_id: 현재 사용자 ID (메시지를 읽는 사람)
            
        Returns:
            dict: {"message": str, "marked_count": int}
        """
        # 내 회원 번호 조회
        my_no_sql = text("SELECT member_no FROM multicampus_schema.member WHERE member_id = :id")
        my_no = db.execute(my_no_sql, {"id": user_id}).scalar()
        
        if not my_no:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        try:
            # SQL: 상대방이 보낸 읽지 않은 메시지를 읽음 처리
            mark_read_sql = text("""
                UPDATE multicampus_schema.talk
                SET confirm_yn = 'Y',
                    update_user = :updater,
                    update_date = CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'
                WHERE talk_room_id = :room_id
                  AND member_no != :my_no
                  AND confirm_yn = 'N'
            """)
            
            result = db.execute(mark_read_sql, {
                "room_id": room_id,
                "my_no": my_no,
                "updater": user_id
            })
            db.commit()
            
            marked_count = result.rowcount
            return {
                "message": f"{marked_count}개의 메시지를 읽음 처리했습니다.",
                "marked_count": marked_count
            }
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"메시지 읽음 처리 실패: {str(e)}")

    @staticmethod
    def unblock_friend(db: Session, my_id: str, friend_id: str):
        """친구 차단 해제
        
        delete_user와 delete_date를 NULL로 설정하여 차단 해제
        
        Returns:
            dict: {"message": str}
        """
        
        # 회원 번호 조회
        get_no_sql = text("SELECT member_no FROM multicampus_schema.member WHERE member_id = :id")
        my_no = db.execute(get_no_sql, {"id": my_id}).scalar()
        friend_no = db.execute(get_no_sql, {"id": friend_id}).scalar()
        
        if not my_no or not friend_no:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        # SQL: 친구 차단 해제 (delete_user와 delete_date를 NULL로 업데이트, 양쪽 member_no 처리, delete_date IS NOT NULL인 경우에만 업데이트)
        unblock_sql = text("""
            UPDATE multicampus_schema.talk_room
            SET delete_date = NULL,
                delete_user = NULL,
                update_date = CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
                update_user = :updater
            WHERE ((member_no1 = :m1 AND member_no2 = :m2) 
                OR (member_no1 = :m2 AND member_no2 = :m1))
              AND delete_date IS NOT NULL
        """)
        
        try:
            # SQL 실행 후 결과 반환 (실제 업데이트된 행 수로 성공 여부 판단)
            result = db.execute(unblock_sql, {
                "m1": my_no, "m2": friend_no, "updater": my_id
            })
            db.commit()
            
            # 업데이트된 행이 없으면(이미 차단 해제된 친구거나 존재하지 않는 친구) 404 에러 반환
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="차단 해제할 친구를 찾을 수 없습니다.")
            
            return {"message": "차단이 해제되었습니다."}
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"차단 해제 실패: {str(e)}")
