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
    hdfs = await get_hdfs()  # HDFS 연결
    # 연결 확인
    try:
        hdfs.content('/')
        logger.info("✅ HDFS 연결됨")
    except Exception as e:
        logger.error(f"❌ HDFS 연결 실패: {e}")
        raise

    yield

    # ===== 종료 시 =====
    logger.info("="*70)
    logger.info("🛑 Hadoop Server Shutting Down...")
    logger.info("✅ HDFS 연결 종료")

# FastAPI 앱 생성
app = FastAPI(title="Hadoop API", version="1.0", lifespan=lifespan)

# API 라우터 등록
app.include_router(hdfs_router, prefix="/hdfs", tags=["Hadoop"])