import redis.asyncio as redis

from app.core.config import settings

# 전역 Redis 클라이언트
redis_client = None

async def get_redis():
    """Redis 클라이언트 반환"""
    global redis_client

    if redis_client is None:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )

    return redis_client

async def close_redis():
    """Redis 연결 종료"""
    global redis_client

    if redis_client is not None:
        await redis_client.close()
        redis_client = None