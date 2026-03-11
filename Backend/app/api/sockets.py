"""Socket.IO 실시간 통신 처리

웹소켓 이벤트 핸들링 및 실시간 메시지 처리
"""
import socketio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import text
from fastapi.concurrency import run_in_threadpool
from jose import jwt, JWTError

from app.core.database import SessionLocal
from app.core.config import settings

# kobart 모델 서버 코드 추가
from app.services.chat_service import ChatService
from app.services.text_preprocessor import normalize_input_text

# 로거 설정
logger = logging.getLogger("socket")
logging.basicConfig(level=logging.INFO)

# Socket.IO 서버 생성
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")


@sio.event
async def connect(sid, environ, auth):
    """클라이언트 연결 (JWT 토큰 검증)"""
    try:
        # auth 딕셔너리에서 토큰 추출
        token = None
        if auth and isinstance(auth, dict):
            token = auth.get("token")
        
        # 토큰이 없으면 연결 거부
        if not token:
            logger.warning(f"❌ [Socket] 토큰 없음 | SID: {sid}")
            return False
        
        # JWT 토큰 검증
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            user_id = payload.get("sub")
            
            if user_id is None:
                logger.warning(f"❌ [Socket] 토큰에 user_id 없음 | SID: {sid}")
                return False
            
            # 세션에 user_id 저장 (나중에 사용 가능)
            await sio.save_session(sid, {"user_id": user_id})
            logger.info(f"✅ [Socket] 접속됨 (인증) | SID: {sid} | User: {user_id}")
            return True
            
        except JWTError as e:
            logger.warning(f"❌ [Socket] JWT 검증 실패 | SID: {sid} | Error: {e}")
            return False
    
    except Exception as e:
        logger.error(f"❌ [Socket] 연결 오류 | SID: {sid} | Error: {e}")
        return False


@sio.on("register_user")
async def handle_register_user(sid, data):
    """사용자 개인 알림 방 등록
    
    각 사용자를 자신의 user_id를 이름으로 하는 방에 join시켜
    개인 알림을 받을 수 있게 함
    """
    user_id = data.get("user_id")
    if user_id:
        await sio.enter_room(sid, f"user_{user_id}")
        logger.info(f"🔔 [알림 등록] {user_id} -> user_{user_id}")


@sio.on("join_room")
async def handle_join_room(sid, data):
    """채팅방 입장"""
    # Socket.IO room key
    room = data.get("room")
    username = data.get("username")
    
    if room and username:
        await sio.enter_room(sid, room)
        logger.info(f"🚪 [입장] {username} -> {room}")
        
        # 채팅방 입장 시 상대방에게 읽음 처리 알림 전송
        await sio.emit("messages_read", {"reader": username}, room=room)
        logger.info(f"✅ [읽음 처리] {username}이(가) {room} 메시지 읽음")


@sio.on("leave_room")
async def handle_leave_room(sid, data):
    """채팅방 퇴장"""
    room = data.get("room")
    username = data.get("username")
    
    if room:
        await sio.leave_room(sid, room)
        logger.info(f"👋 [퇴장] {username} <- {room}")


@sio.on("notify_read")
async def handle_notify_read(sid, data):
    """메시지 읽음 알림 (상대방이 메시지를 읽었을 때)"""
    room = data.get("room")
    reader = data.get("reader")
    
    if room and reader:
        # 같은 방에 있는 사람들에게 읽음 처리 알림
        await sio.emit("messages_read", {"reader": reader}, room=room)
        logger.info(f"✅ [실시간 읽음] {reader}이(가) {room} 메시지 읽음 알림 전송")


def get_receiver_id(room_id: int, sender_id: str):
    """채팅방의 상대방 user_id 조회 (동기 함수)
    
    Returns:
        str: 수신자 user_id
    """
    db = SessionLocal()
    try:
        # room_id로부터 두 참여자 조회
        query = text("""
            SELECT DISTINCT m.member_id
            FROM multicampus_schema.talk t
            JOIN multicampus_schema.member m ON t.member_no = m.member_no
            WHERE t.talk_room_id = :room_id
            AND m.member_id != :sender_id
            LIMIT 1
        """)
        result = db.execute(query, {"room_id": room_id, "sender_id": sender_id}).fetchone()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"❌ [DB 에러] 수신자 조회 실패: {e}")
        return None
    finally:
        db.close()


def save_message_sync(room_id: int, sender_id: str, msg: str):
    """채팅 메시지 DB 저장 (동기 함수)
    
    Returns:
        str: 발신자 이름 (full_name)
    """
    db = SessionLocal()
    try:
        # 사용자 정보 조회
        get_user_sql = text("SELECT member_no, full_name FROM multicampus_schema.member WHERE member_id = :id")
        user_info = db.execute(get_user_sql, {"id": sender_id}).fetchone()
        
        if not user_info:
            logger.warning(f"⚠️ [DB 저장 실패] 존재하지 않는 사용자: {sender_id}")
            return None

        member_no, sender_name = user_info[0], user_info[1]

        # 메시지 저장
        insert_sql = text("""
            INSERT INTO multicampus_schema.talk (
                talk_room_id, member_no, talk_date, message, create_user
            ) VALUES (
                :r_id, :m_no, CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul', :msg, :c_user
            )
        """)
        
        db.execute(insert_sql, {
            "r_id": room_id,
            "m_no": member_no,
            "msg": msg,
            "c_user": sender_id
        })        
        db.commit()
        
        return sender_name

    except Exception as e:
        logger.error(f"[DB 에러] 메시지 저장 실패: {e}")
        db.rollback()
        raise
    finally:
        db.close()

# 영상 저장을 위해 추가
def save_message_with_key_sync(room_id: int, sender_id: str, msg: str):
    """talk 저장 + talk_detail 저장에 필요한 키(member_no, talk_date)까지 반환 (동기)

    Returns:
        dict | None: {"sender_name": str, "member_no": int, "talk_date": datetime}
    """
    db = SessionLocal()
    try:
        get_user_sql = text(
            "SELECT member_no, full_name FROM multicampus_schema.member WHERE member_id = :id"
        )
        user_info = db.execute(get_user_sql, {"id": sender_id}).fetchone()
        if not user_info:
            logger.warning(f"[DB 저장 실패] 존재하지 않는 사용자: {sender_id}")
            return None

        member_no, sender_name = user_info[0], user_info[1]

        insert_sql = text("""
            INSERT INTO multicampus_schema.talk (
                talk_room_id, member_no, talk_date, message, create_user
            ) VALUES (
                :r_id, :m_no, CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul', :msg, :c_user
            )
            RETURNING talk_date
        """)

        talk_date = db.execute(insert_sql, {
            "r_id": room_id,
            "m_no": member_no,
            "msg": msg,
            "c_user": sender_id
        }).scalar()

        db.commit()

        return {"sender_name": sender_name, "member_no": member_no, "talk_date": talk_date}

    except Exception as e:
        db.rollback()
        logger.error(f"[DB 에러] talk_detail 저장 실패: {e}")
        raise
    finally:
        db.close()


def save_talk_detail_sync(
    talk_room_id: int,
    member_no: int,
    talk_date,
    gloss: Optional[str],
    urls: list,
    miss: list[str],
    create_user: str
):
    """
    talk_detail 저장 (동기)

    - 식별 키: (talk_room_id, member_no, talk_date)
    - 정렬 키: word_order_no (1부터)

    정책:
    - url 매칭된 토큰만 저장
    - miss 토큰은 저장하지 않음
    - urls는 "매칭된 토큰 순서대로" 들어온다고 가정하고,
      miss 토큰을 건너뛰면서 url 인덱스를 소비한다.
    """
    if not gloss:
        return 0

    tokens = [t for t in gloss.split() if t.strip()]
    if not tokens:
        return 0

    miss_set = set(miss or [])

    db = SessionLocal()
    try:
        insert_sql = text("""
            INSERT INTO multicampus_schema.talk_detail (
                talk_room_id,
                member_no,
                talk_date,
                word_order_no,
                word_name,
                url_path,
                vector,
                create_user,
                create_date
            ) VALUES (
                :talk_room_id,
                :member_no,
                :talk_date,
                :word_order_no,
                :word_name,
                :url_path,
                :vector,
                :create_user,
                CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'
            )
        """)

        rows = 0
        order_no = 1
        url_idx = 0

        for word in tokens:
            # 매핑 실패 토큰은 저장 대상 아님
            if word in miss_set:
                continue

            # 매칭된 토큰에 대해서만 urls를 순서대로 소비
            if url_idx >= len(urls):
                break

            url_path = urls[url_idx]
            url_idx += 1

            if not url_path:
                continue

            db.execute(insert_sql, {
                "talk_room_id": talk_room_id,
                "member_no": member_no,
                "talk_date": talk_date,
                "word_order_no": order_no,
                "word_name": word,
                "url_path": url_path,
                "vector": "[]",
                "create_user": create_user
            })
            rows += 1
            order_no += 1

        db.commit()
        return rows

    except Exception as e:
        db.rollback()
        logger.error(f"[DB 에러] talk_detail 저장 실패: {e}")
        raise
    finally:
        db.close()


@sio.on("send_message")
async def handle_send_message(sid, data):
    """메시지 전송 처리
    
    1. DB에 메시지 저장
    2. 같은 방에 있는 모든 클라이언트에게 브로드캐스트
    3. 상대방의 개인 알림 방으로도 알림 전송
    """
    # join_room에서와 통일시키기 위해서 Socket.IO room key 추가
    room = data.get("room")
    room_id = data.get("room_id")
    sender_id = data.get("username")
    msg = data.get("message")

    # 한국 시간 (KST = UTC+9)
    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST).strftime("%H:%M")

    if room and sender_id and msg:
        try:
            # DB 저장 (별도 스레드)
            # sender_name = await run_in_threadpool(save_message_sync, room_id, sender_id, msg)
            saved = await run_in_threadpool(save_message_with_key_sync, room_id, sender_id, msg)
            if not saved:
                return
            
            sender_name = saved["sender_name"]
            member_no = saved["member_no"]
            talk_date = saved["talk_date"]
            
            # 추가 model_server 전달 검증 로그
            trace_id = uuid.uuid4().hex[:8]
            t0 = time.time()

            logger.info(
            "[WS -> Model][%s] start room_id=%s sid=%s msg_len=%d",
            trace_id, room_id, sid, len(msg)
        )

            msg_norm = normalize_input_text(msg)

            result = await run_in_threadpool(ChatService.text_to_gloss_and_urls_sync, msg_norm)

            if not isinstance(result, dict):
                logger.error("[WS] ChatService returned non-dict: %r", result)
                result = {"gloss": None, "urls": [], "miss": [], "meta": None}

            gloss = result.get("gloss")
            urls = result.get("urls", [])
            miss = result.get("miss", [])

            saved_rows = await run_in_threadpool(
            save_talk_detail_sync,
            room_id,
            member_no,
            talk_date,
            gloss,
            urls,
            miss,
            sender_id
        )

            logger.info(
                "[DB] talk_detail saved_rows=%d room_id=%s member_no=%s talk_date=%s",
                saved_rows, room_id, member_no, talk_date
            )

            msg_preview = (msg[:30] + "...") if len(msg) > 30 else msg
            logger.info(
                "[GLOSS] msg_preview=%r gloss=%r url_cnt=%d miss_cnt=%d",
                msg_preview, gloss, len(urls), len(miss)
            )

            elapsed_ms = int((time.time() - t0) * 1000)
            logger.info(
                "[WS -> Model][%s] done elapsed_ms=%d gloss_len=%d url_cnt=%d miss_cnt=%d",
                trace_id, elapsed_ms, (len(gloss) if gloss else 0), len(urls), len(miss)
                )

            # 실시간 전송
            if sender_name:
                payload = {
                    "sender": sender_id,
                    "sender_name": sender_name,
                    "message": msg,
                    # 추가
                    "gloss": gloss,
                    "urls": urls,
                    "miss": miss,
                    "time": now_kst
                }

                # 송출 로그(단일 payload)
                logger.info(
                    "[SOCKET OUT] keys=%s url_cnt=%s miss_cnt=%s",
                    list(payload.keys()),
                    len(urls),
                    len(miss)
                )

                # 1. 같은 방에 있는 사용자들에게 메시지 전송
                await sio.emit("receive_message", payload, room=room)
                
                # 2. 상대방에게 읽지 않은 메시지 알림 전송
                receiver_id = await run_in_threadpool(get_receiver_id, room_id, sender_id)
                if receiver_id:
                    await sio.emit("unread_notification", {
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "room_id": room_id
                    }, room=f"user_{receiver_id}")
                    logger.info(f"🔔 [알림 전송] {sender_id} -> user_{receiver_id}")
                
        except Exception as e:
            logger.exception("❌ [소켓 에러] 메시지 처리 실패")

@sio.on("send_translation")
async def handle_send_translation(sid, data):
    room_id = data.get("room_id")
    room_name = data.get("room")
    sender_id = data.get("username")
    msg = data.get("message")

    # 한국 시간 (KST = UTC+9)
    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST).strftime("%H:%M")
    
    if room_id and sender_id and msg:
        try:
            # DB 저장 (별도 스레드)
            sender_name = await run_in_threadpool(save_message_sync, room_id, sender_id, msg)

            # 실시간 전송
            if sender_name:
                payload = {
                    "sender": sender_id,
                    "sender_name": sender_name,
                    "message": msg,
                    "time": now_kst
                }
                
                # 1. 같은 방에 있는 사용자들에게 메시지 전송
                await sio.emit("receive_message", payload, room=room_name)
                
                # 2. 상대방에게 읽지 않은 메시지 알림 전송
                receiver_id = await run_in_threadpool(get_receiver_id, room_id, sender_id)
                if receiver_id:
                    await sio.emit("unread_notification", {
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "room_id": room_id
                    }, room=f"user_{receiver_id}")
                    logger.info(f"🔔 [알림 전송] {sender_id} -> user_{receiver_id}")
                
        except Exception as e:
            logger.exception("❌ [소켓 에러] 메시지 처리 실패")
