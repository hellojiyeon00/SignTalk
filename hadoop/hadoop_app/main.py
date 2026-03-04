"""FastAPI Hadoop 애플리케이션"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from hadoop_app.core.hdfs_client import get_hdfs
from hadoop_app.api.hdfs import router as hdfs_router

logger = logging.getLogger("hdfs-server")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ===== 시작 시 =====
    logger.info("="*70)
    logger.info("🚀 Hadoop Server Starting...")
    logger.info("="*70)

    # HDFS
    try:
        hdfs = await get_hdfs()
        hdfs.content('/')
        logger.info("✅ HDFS 연결됨")
    except Exception as e:
        logger.warning(f"⚠️  HDFS 연결 실패 (서버 미가동 또는 네트워크 문제): {e}")
        logger.warning("⚠️  HDFS 없이 서버를 시작합니다. HDFS 관련 API는 동작하지 않습니다.")

    yield

    # ===== 종료 시 =====
    logger.info("="*70)
    logger.info("🛑 Hadoop Server Shutting Down...")
    logger.info("✅ HDFS 연결 종료")

# FastAPI 앱 생성
app = FastAPI(title="Hadoop API", version="1.0", lifespan=lifespan)

# API 라우터 등록
app.include_router(hdfs_router, prefix="/hdfs", tags=["Hadoop"])