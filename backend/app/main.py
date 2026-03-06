"""FastAPI 메인 애플리케이션

Socket.IO를 지원하는 채팅 서버 설정
"""
import asyncio
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import os


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
        #
        import app.services.disaster_service as ds
        ds.kafka_listener_task = asyncio.create_task(DisasterService.start_disaster_listener())
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

# 프론트엔드 정적 파일 서빙 (루트 경로)
# 경로: SignTalk/backend/app/main.py 기준 SignTalk/frontend
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
    logger.info(f"✅ Frontend 연결됨")
else:
    logger.warning(f"⚠️ Frontend 경로 확인 불가: {frontend_path}")

# 재난 이미지 정적 파일 서빙
app.mount("/images", StaticFiles(directory="../image"), name="images")

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
    
    logger.info("✅ 서버 종료 완료")

# Socket.IO 통합 - app과 sio를 연결하여 Socket.IO 서버로 FastAPI 앱을 감쌈
app = socketio.ASGIApp(sio, app)


