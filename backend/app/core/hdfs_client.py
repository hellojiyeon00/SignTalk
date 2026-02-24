from hdfs import InsecureClient

from app.core.config import settings

# 전역 HDFS 클라이언트
hdfs_client = None

async def get_hdfs():
    """HDFS 클라이언트 반환"""
    global hdfs_client

    if hdfs_client is None:
        hdfs_client = InsecureClient(settings.HDFS_URL, user=settings.HDFS_USER, timeout=5)

    return hdfs_client