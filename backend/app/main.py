"""FastAPI 메인 애플리케이션

Socket.IO를 지원하는 채팅 서버 설정
"""
import asyncio
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.redis_client import get_redis, close_redis
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.disaster import router as disaster_router
from app.api.location import router as location_router
from app.api.sockets import sio
from app.services.disaster_service import DisasterService

logger = logging.getLogger("backend-server")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ===== 시작 시 =====

    # Redis
    redis = await get_redis()  # Redis 연결
    # 연결 확인
    try:
        await redis.ping()
        logger.info("✅ Redis 연결됨")
    except Exception as e:
        logger.error(f"❌ Redis 연결 실패: {e}")
        raise

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

# 서버 시작 시 실행할 초기화 작업 (비동기)
@app.on_event("startup") 
async def startup_event():
    # SSE 재난문자 리스너를 백그라운드에서 가동
    asyncio.create_task(DisasterService.start_disaster_listener())

# Socket.IO 통합 - app과 sio를 연결하여 Socket.IO 서버로 FastAPI 앱을 감쌈
app = socketio.ASGIApp(sio, app)
