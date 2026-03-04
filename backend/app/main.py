"""FastAPI 메인 애플리케이션"""
import asyncio
import logging
from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.disaster import router as disaster_router
from app.api.location import router as location_router
from app.api.sockets import sio
from app.core.config import settings
from app.core.redis_client import close_redis, get_redis
from app.services.disaster_service import DisasterService
import app.services.disaster_service as ds

logger = logging.getLogger("backend-server")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 시작 ──────────────────────────────────────────────────────
    redis = await get_redis()
    try:
        await redis.ping()
        logger.info("✅ Redis 연결됨")
    except Exception as e:
        logger.error(f"❌ Redis 연결 실패: {e}")
        raise

    ds.kafka_listener_task = asyncio.create_task(
        DisasterService.start_disaster_listener()
    )

    yield

    # ── 종료 ──────────────────────────────────────────────────────
    logger.info("🛑 서버 종료 중...")
    await DisasterService.stop_disaster_listener()
    await close_redis()
    logger.info("✅ 서버 종료 완료")


app = FastAPI(title="SignTalk API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,     prefix="/auth",     tags=["인증"])
app.include_router(chat_router,     prefix="/chat",     tags=["채팅"])
app.include_router(disaster_router, prefix="/disaster", tags=["재난문자"])
app.include_router(location_router, prefix="/location", tags=["위치"])

if getattr(settings, "DEBUG", False):
    from app.api.test_disaster import router as test_disaster_router
    app.include_router(test_disaster_router, prefix="/disaster/test", tags=["테스트"])
    logger.info("🧪 DEBUG 모드: /disaster/test 라우터 활성화")

# Socket.IO ASGI 래핑 (반드시 마지막에)
app = socketio.ASGIApp(sio, app)
