import json
import logging

from app.core.redis_client import get_redis

# 로거 설정
logger = logging.getLogger("redis-service")
logging.basicConfig(level=logging.INFO)

# Redis에 저장된 프레임은 600초(10분) 후 자동 삭제
TTL = 600

# Redis 키 생성 함수
# 유저별로 Redis 키를 다르게 생성
def frame_key(room_id, sender_id):
    return f"sign:{room_id}:{sender_id}:frames"

# 프레임 저장 함수
async def push_frame(room_id, sender_id, landmarks):
    redis = await get_redis()
    key = frame_key(room_id, sender_id)

    # Redis List에 프레임 추가(JSON으로 변환 및 저장)
    await redis.rpush(key, json.dumps(landmarks))
    # TTL 갱신(메모리 누수 방지)
    await redis.expire(key, TTL)

# ===== Redis 작업 =====
async def get_frames(room_id, sender_id):
    """Redis에 저장된 프레임 반환"""
    redis = await get_redis()
    key = frame_key(room_id, sender_id)

    frames = await redis.lrange(key, 0, -1)

    return [json.loads(f) for f in frames]

async def clear_session(room_id, sender_id):
    """세션 정리"""
    redis = await get_redis()
    
    await redis.delete(
        frame_key(room_id, sender_id)
    )
    
    logger.info(f"🗑️ [Clear] {room_id}:{sender_id} - 세션 정리 완료")