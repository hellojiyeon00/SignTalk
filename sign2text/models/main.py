"""FastAPI Model 애플리케이션"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from model_app.core.redis_client import get_redis, close_redis
from model_app.core.model_loader import ModelLoader
from model_app.api.models import router as model_router

logger = logging.getLogger("model-server")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ===== 시작 시 =====
    logger.info("="*70)
    logger.info("🚀 Sign Language Model Server Starting...")
    logger.info("="*70)
    
    # 1. 모델 로드 (최초 1회)
    try:
        ModelLoader.initialize_all()
    except Exception as e:
        logger.error(f"❌ 모델 로딩 실패: {e}")
        raise
    
    # 2. Redis 연결
    redis = await get_redis()
    try:
        await redis.ping()
        logger.info("✅ Redis 연결됨")
    except Exception as e:
        logger.error(f"❌ Redis 연결 실패: {e}")
        raise

    # 3. 모델 상태 확인
    status = ModelLoader.get_model_status()
    logger.info("="*70)
    logger.info("📊 모델 서버 준비 완료:")
    logger.info(f"  - LSTM: {'✅' if status['lstm'] else '❌'}")
    logger.info(f"  - Redis: ✅")
    logger.info("="*70)
    
    yield
    
    # ===== 종료 시 =====
    logger.info("="*70)
    logger.info("🛑 Sign Language Model Server Shutting Down...")

    # 모델 언로드 (메모리 정리)
    ModelLoader.unload_all()

    # Redis 종료
    await close_redis()
    logger.info("✅ Redis 연결 종료")
    logger.info("="*70)

# FastAPI 앱 생성
app = FastAPI(title="Model API", version="1.0", lifespan=lifespan)

# API 라우터 등록
app.include_router(model_router, prefix="/models", tags=["Sign2Text"])