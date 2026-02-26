"""Socket.IO 실시간 통신 처리

웹소켓 이벤트 핸들링 및 실시간 메시지 처리
"""
import socketio
import logging
import httpx
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from fastapi.concurrency import run_in_threadpool
<<<<<<< HEAD

from app.core.database import SessionLocal
from app.services.sign_service import call_sign2text
=======
from jose import jwt, JWTError

from app.core.database import SessionLocal
from app.services.sign_service import transfer_sign2gloss
from app.core.config import settings
>>>>>>> origin/feature/chat

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
    3. 상대방의 개인 알림 방으로도 알림 전송
    """
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
            logger.error(f"❌ [소켓 에러] 메시지 처리 실패: {e}")

# 랜드마크 수신
@sio.on("send_landmarks")
async def handle_send_landmarks(sid, data):
    # 서비스 호출 (AI 모델 예측 및 단어 추출)
    sign_data = await call_sign2text(data)

<<<<<<< HEAD
    if sign_data is not None:
        room_id = data.get("room_id")
        room_name = data.get("room")
        sender_id = data.get("username")
        msg = sign_data["message"]
=======
    """메시지 전송 처리
    
    1. DB에 메시지 저장
    2. 같은 방에 있는 모든 클라이언트에게 브로드캐스트
    3. 상대방의 개인 알림 방으로도 알림 전송
    """
    room_id = data.get("room_id")
    room_name = data.get("room")
    sender_id = data.get("username")
    msg = msg
>>>>>>> origin/feature/chat

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
                        "time": sign_data["time"]
                    }
                
<<<<<<< HEAD
                    await sio.emit("receive_message", payload, room=room_name)

            except Exception as e:
                logger.error(f"❌ [소켓 에러] 메시지 처리 실패: {e}")
=======
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
            logger.error(f"❌ [소켓 에러] 메시지 처리 실패: {e}")
>>>>>>> origin/feature/chat
