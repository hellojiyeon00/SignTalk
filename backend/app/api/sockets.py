"""Socket.IO 실시간 통신 처리

웹소켓 이벤트 핸들링 및 실시간 메시지 처리
"""
import socketio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from fastapi.concurrency import run_in_threadpool

from app.core.database import SessionLocal
# kobart 모델 서버 코드 추가 (소영)
from app.services.chat_service import ChatService
from app.services.text_preprocessor import normalize_input_text

from app.services.sign_service import transfer_sign2gloss

# 로거 설정
logger = logging.getLogger("socket")
logging.basicConfig(level=logging.INFO)

# Socket.IO 서버 생성
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")


@sio.event
async def connect(sid, environ):
    """클라이언트 연결"""
    logger.info(f"✅ [Socket] 접속됨 | SID: {sid}")


@sio.on("join_room")
async def handle_join_room(sid, data):
    """채팅방 입장"""
    # Socket.IO room key (소영)
    room = data.get("room")
    username = data.get("username")
    
    if room and username:
        await sio.enter_room(sid, room)
        logger.info(f"🚪 [입장] {username} -> {room}")


@sio.on("leave_room")
async def handle_leave_room(sid, data):
    """채팅방 퇴장"""
    room = data.get("room")
    username = data.get("username")
    
    if room:
        await sio.leave_room(sid, room)
        logger.info(f"👋 [퇴장] {username} <- {room}")


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
        logger.error(f"❌ [DB 에러] 메시지 저장 실패: {e}")
        db.rollback()
        raise e
    finally:
        db.close()

@sio.on("send_message")
async def handle_send_message(sid, data):
    """메시지 전송 처리
    
    1. DB에 메시지 저장
    2. 같은 방에 있는 모든 클라이언트에게 브로드캐스트
    """
    # join_room에서와 통일시키기 위해서 Socket.IO room key 추가 (소영)
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
            sender_name = await run_in_threadpool(save_message_sync, room_id, sender_id, msg)
            # 추가 model_server 전달 검증 로그 (소영)
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
                    # 추가 (소영)
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

                # 같은 방 모두에게 동일 payload breadcast
                await sio.emit("receive_message", payload, room=room)
                
        except Exception as e:
            logger.error(f"❌ [소켓 에러] 메시지 처리 실패: {e}")

# 랜드마크 수신
@sio.on("send_landmarks")
async def handle_send_landmarks(sid, data):
    # 1. 서비스 호출 (AI 모델 예측 및 단어 추출)
    # data 안에는 username, room, message(좌표) 등이 들어있음
    msg = await transfer_sign2gloss(data)

    """메시지 전송 처리
    
    1. DB에 메시지 저장
    2. 같은 방에 있는 모든 클라이언트에게 브로드캐스트
    """
    room_id = data.get("room_id")
    room_name = data.get("room")
    sender_id = data.get("username")
    msg = msg

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
                
                await sio.emit("receive_message", payload, room=room_name)
                
        except Exception as e:
            logger.exception("❌ [소켓 에러] 메시지 처리 실패")
            # logger.error(f"❌ [소켓 에러] 메시지 처리 실패: {e}")