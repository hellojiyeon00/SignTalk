import json
import httpx
import logging
from datetime import datetime

from app.core.redis_client import get_redis
# from app.services.llm_service import transfer_gloss2text

# 로거 설정
logger = logging.getLogger("sign-service")
logging.basicConfig(level=logging.INFO)

MODEL_API_BASE_URL = "http://127.0.0.1:8004"

# Redis에 저장된 프레임은 600초(10분) 후 자동 삭제
TTL = 600

# Redis 키 생성 함수
# 유저별로 Redis 키를 다르게 생성
def frame_key(room_id, sender_id):
    return f"sign:{room_id}:{sender_id}:frames"

# 프레임 저장 함수
async def push_frame(room_id, sender_id, landmarks):
    redis = await get_redis()
    key = frame_key(room_id, sender_id)

    # Redis List에 프레임 추가(JSON으로 변환 및 저장)
    await redis.rpush(key, json.dumps(landmarks))
    # TTL 갱신(메모리 누수 방지)
    await redis.expire(key, TTL)

    # ✅ 저장 확인 (디버깅용)
    length = await redis.llen(key)
    print(f"[DEBUG] Redis key={key} 저장 완료. 현재 프레임 수: {length}")

async def clear_session(room_id, sender_id):
    """세션 정리"""
    redis = await get_redis()
    
    await redis.delete(
        frame_key(room_id, sender_id)
    )
    
    logger.info(f"🗑️ [Clear] {room_id}:{sender_id} - 세션 정리 완료")

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
        url = f"{MODEL_API_BASE_URL}/models/sign2text"

        try:
            timeout = httpx.Timeout(15.0, connect=5.0)  # 너무 오래 안 기다리게
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json={"room_id": room_id, "username": sender_id})
                
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
                
                    # 하둡 저장을 위한 페이로드 구성
                    # coordinates_Hadoop.py의 C_Hadoop 클래스 구조에 맞춤
                    hadoop_payload = {
                        "v_member_no": data.get("member_no"), # 유저 고유 번호
                        "v_talk_date": datetime.now().isoformat(), # 현재 시간
                        "v_message": korean_text, # 번역된 최종 문장
                        "v_coordinates": all_landmarks # 저장할 전체 랜드마크 리스트
                    }
                
                    # 하둡 저장 API 호출
                    try:
                        async with httpx.AsyncClient() as client:
                            h_resp = await client.post(HADOOP_API_URL, json=hadoop_payload)
                            if h_resp.status_code == 200:
                                logger.info(f"💾 [HDFS] 데이터 저장 완료: {h_resp.json().get('hdfs_path')}")
                    except Exception as e:
                        logger.error(f"❌ [HDFS] 저장 실패: {e}")

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