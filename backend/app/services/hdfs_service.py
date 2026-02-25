import json
import logging
from datetime import datetime

from app.core.hdfs_client import get_hdfs
from app.services.redis_service import get_frames

# 로거 설정
logger = logging.getLogger("hdfs-service")
logging.basicConfig(level=logging.INFO)

HDFS_BASE = '/DFCS'

def build_hdfs_path(member_id, talk_date):
    """
    마이크로초를 활용한 고유 파일명 생성
    """
    dt = datetime.fromisoformat(talk_date)
    time_str = dt.strftime('%Y%m%d_%H%M%S')
    part = int(dt.microsecond / 10000)
    filename = f'{time_str}{part:02d}.json'

    return f'{HDFS_BASE}/{member_id}/{filename}'

async def save_hdfs(room_id, member_id, talk_date, message):
    """
    수어 번역 데이터와 랜드마크 좌표를 HDFS에 저장
    """
    try:
        hdfs = await get_hdfs()

        # 파일명 및 경로 설정
        hdfs_path = build_hdfs_path(member_id, talk_date)

        # redis에 저장된 랜드마크 로드
        coordinates = await get_frames(room_id, member_id)

        # 저장 데이터 구성
        payload = {
            "v_member_no": member_id,
            "v_talk_data": talk_date,
            "v_message": message,
            "v_coordinates": coordinates
        }

        # HDFS 파일 쓰기(JSON 직렬화)
        with hdfs.write(hdfs_path, encoding='utf-8', overwrite=True) as writer:
            json.dump(payload, writer, ensure_ascii=False)

        logger.info(f"💾 [HDFS] 저장 성공: {hdfs_path}")
        return None

    except Exception as e:
        logger.error(f"❌ [HDFS] 저장 중 오류 발생: {str(e)}")
        return None