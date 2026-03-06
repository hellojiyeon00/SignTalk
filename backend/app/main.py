"""FastAPI 메인 애플리케이션"""
import asyncio
import logging
from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
        #
        import app.services.disaster_service as ds
        ds.kafka_listener_task = asyncio.create_task(DisasterService.start_disaster_listener())
    except Exception as e:
        logger.error(f"❌ Redis 연결 실패: {e}")
        raise

    ds.kafka_listener_task = asyncio.create_task(
        DisasterService.start_disaster_listener()
    )

    yield

    # ===== 종료 시 =====
    await close_redis()
    print("✅ Redis 연결 종료")

# FastAPI 앱 생성
app = FastAPI(title="Chat API", version="1.0.0", lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 모든 도메인 허용
    allow_methods=["*"], # 모든 HTTP 메서드(POST, GET 등) 허용
    allow_headers=["*"], # 모든 HTTP 헤더(Authorization, Content-Type 등) 허용
)

# API 라우터 등록
app.include_router(auth_router, prefix="/auth", tags=["인증"]) # 인증 관련 API는 /auth 경로로 접근
app.include_router(chat_router, prefix="/chat", tags=["채팅"]) # 채팅 관련 API는 /chat 경로로 접근
app.include_router(disaster_router, prefix="/disaster", tags=["재난문자"]) # 재난문자 관련 API는 /disaster 경로로 접근
app.include_router(location_router, prefix="/location", tags=["위치"]) # 위치 관련 API는 /location 경로로 접근

# 재난 이미지 정적 파일 서빙
app.mount("/images", StaticFiles(directory="/app/image"), name="images")

# 서버 시작 시 실행할 초기화 작업 (비동기)
# @app.on_event("startup") 
# async def startup_event():
#     # SSE 재난문자 리스너를 백그라운드에서 가동
#     from app.services.disaster_service import kafka_listener_task
#     import app.services.disaster_service as ds
    # ds.kafka_listener_task = asyncio.create_task(DisasterService.start_disaster_listener())



# 서버 종료 시 실행할 정리 작업 (비동기)
@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 모든 연결과 리소스를 정리합니다."""
    import logging
    logger = logging.getLogger("main")
    logger.info("🛑 서버 종료 시작...")
    
    # Kafka 리스너 및 SSE 연결 정리
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
