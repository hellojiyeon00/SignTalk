import os
from dotenv import load_dotenv
import httpx
import logging
from datetime import datetime, timedelta, timezone

from app.services.redis_service import push_frame, get_frames, clear_session

# 로거 설정
logger = logging.getLogger("sign-service")
logging.basicConfig(level=logging.INFO)

# .env 파일 로드
load_dotenv()

# 모델 서버 주소
MODEL_API_URL = f"{os.getenv('SIGN_BASE_URL')}/models/sign2text"
# 하둡 서버 주소
HADOOP_API_URL = f"{os.getenv('HADOOP_BASE_URL')}/hdfs/save_hdfs"

# 랜드마크 -> 텍스트 변환(모델 서버 전달)
async def call_sign2text(data):
    """
    전달받은 landmarks를 모델에 넣고 gloss 반환
    """
    room_id = data.get("room_id")
    sender_id = data.get("username")
    landmarks = data.get("message")
    stop = data.get("status_stop") # True: 전송 종료, False: 전송 중

    # 종료 버튼(stopBtn) 눌렀을 때
    if stop:
        try:
            timeout = httpx.Timeout(15.0, connect=5.0)  # 너무 오래 안 기다리게
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(MODEL_API_URL, json={"room_id": room_id, "username": sender_id})
                
                # 응답 상태 확인
                if resp.status_code == 200:
                    result = resp.json()

                    # 모델 서버 응답 데이터 로그 출력
                    # 모델 서버가 반환하는 형태: {"status": "ok", "gloss_sequence": [...], "korean_text": "..."}
                    logger.info(f"✅ [Model Server] 응답 성공")
                    logger.info(f"📊 [Gloss Sequence] {result.get('gloss_sequence')}")
                    logger.info(f"📝 [Korean Text] {result.get('korean_text')}")

                    korean_text = result.get("korean_text")
                    all_landmarks = await get_frames(room_id, sender_id)

                    if korean_text and all_landmarks:
                        # 한국 시간 (KST = UTC+9)
                        KST = timezone(timedelta(hours=9))
                        v_talk_date = datetime.now(KST).isoformat()

                        # 하둡 전송
                        hadoop_payload = {
                            "v_member_no": sender_id,
                            "v_talk_date": v_talk_date,
                            "v_message": korean_text,
                            "v_coordinates": all_landmarks
                        }

                        try:
                            h_resp = await client.post(HADOOP_API_URL, json=hadoop_payload, timeout=10.0)
                            
                            if h_resp.status_code == 200:
                                h_result = h_resp.json()
                                h_status = h_result.get("status")
                                h_detail = h_result.get("detail")
                                logger.info(f"✅ [Hadoop Server] {h_status}: {h_detail}")
                            else:
                                logger.error(f"❌ [Hadoop Server] 응답 에러: {h_resp.status_code}")

                        except Exception as e:
                            logger.error(f"❌ [Hadoop Server] 통신 실패: {e}")
                        
                        # 세션 정리
                        await clear_session(room_id, sender_id)
                        return korean_text

                else:
                    logger.error(f"❌ [Model Server] 응답 실패 (Code: {resp.status_code})")
                    # 세션 정리
                    await clear_session(room_id, sender_id)
                    return None

        except httpx.ReadTimeout:
            logger.error("❌ [Model Server] 응답 시간 초과 (Timeout)")

        except Exception as e:
            logger.error(f"❌ [Model Server] 통신 오류: {repr(e)}")

        # 세션 정리
        await clear_session(room_id, sender_id)
        return None
    
    # 프레임 저장
    await push_frame(room_id, sender_id, landmarks)
    return None