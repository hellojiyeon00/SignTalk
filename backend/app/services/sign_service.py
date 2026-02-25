import httpx
import logging

from app.services.redis_service import push_frame, clear_session

# 로거 설정
logger = logging.getLogger("sign-service")
logging.basicConfig(level=logging.INFO)

MODEL_API_BASE_URL = "http://127.0.0.1:8004"

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