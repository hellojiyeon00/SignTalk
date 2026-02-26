import json
import logging
from datetime import datetime
from pydantic import BaseModel
import os

from hadoop_app.core.hdfs_client import get_hdfs

# 로거 설정
logger = logging.getLogger("hdfs-service")
logging.basicConfig(level=logging.INFO)

v_hdfs_base = '/DFCS'

# .../hadoop/DFCS/ 경로에 파일 저장
_current_file = os.path.abspath(__file__)
v_local_base = os.path.dirname(os.path.dirname(os.path.dirname(_current_file)))

class C_Hadoop(BaseModel):
    v_member_no:str
    v_talk_date:str
    v_message:str
    v_coordinates:list

def f_build_hdfs_path(a_member_no,a_talk_date):
    """
    마이크로초를 활용한 고유 파일명 생성
    """
    v_dt = datetime.fromisoformat(a_talk_date)
    v_time_str = v_dt.strftime('%Y%m%d_%H%M%S')
    v_part = int(v_dt.microsecond / 10000)
    v_filename = f'{v_time_str}{v_part:02d}.json'
    v_path = f'{v_hdfs_base}/{a_member_no}/{v_filename}'

    return v_path

async def f_save_hdfs(a_data:C_Hadoop):
    """
    수어 번역 데이터와 랜드마크 좌표를 HDFS에 저장
    """
    try:
        hdfs = await get_hdfs()

        a_member_no = a_data.v_member_no
        a_talk_date = a_data.v_talk_date

        # 파일명 및 경로 설정
        hdfs_path = f_build_hdfs_path(a_member_no, a_talk_date)

        # HDFS 파일 쓰기
        with hdfs.write(hdfs_path, encoding='utf-8', overwrite=True) as writer:
            json.dump(a_data.model_dump(), writer, ensure_ascii=False)

        logger.info(f"💾 [HDFS] 저장 성공: {hdfs_path}")
        return {"status": "success", "detail": hdfs_path}

    except Exception as e:
        logger.error(f"❌ [HDFS] 저장 중 오류 발생: {str(e)}")
        return {"status": "fail", "detail": str(e)}