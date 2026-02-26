import json
import logging
import numpy as np

from model_app.core.redis_client import get_redis
from model_app.core.config import settings
from model_app.core.model_loader import ModelLoader
from model_app.services.llm_service import translate_gloss2text

# 로거 설정
logger = logging.getLogger("lstm-service")
logging.basicConfig(level=logging.INFO)

# ===== Redis 키 생성 =====
def frame_key(room_id, sender_id):
    """프레임 저장 키"""
    return f"sign:{room_id}:{sender_id}:frames"

# ===== Redis 작업 =====
async def get_frames(room_id, sender_id):
    """Redis에 저장된 프레임 반환"""
    redis = await get_redis()
    key = frame_key(room_id, sender_id)

    frames = await redis.lrange(key, 0, -1)

    return [json.loads(f) for f in frames]

# ===== LSTM 예측 =====
def predict_gloss(frame_list, window_size):
    """
    슬라이딩 윈도우 기법으로 글로스 시퀀스 예측
    """
    # 모델 확인
    if ModelLoader.lstm_model is None:
        logger.error("❌ [LSTM] 모델이 로드되지 않음")
        return None
    
    n = len(frame_list)
    
    # 프레임 수 확인
    if n < window_size:
        logger.warning(f"⚠️ [LSTM] 프레임 부족: {n} < {window_size}")
        return None
    
    gloss_seq = []
    last_gloss = None
    
    logger.info(f"🔮 [LSTM] 슬라이딩 윈도우 시작 (총 {n}프레임, 윈도우={window_size})")
    
    # 슬라이딩 윈도우
    for i in range(0, n - window_size + 1, 8):
        # 윈도우 추출 (8프레임)
        window = frame_list[i:i + window_size]  # shape: (8, 84)
        
        # 모델 입력 형태로 변환 (1, 8, 84)
        window_input = np.expand_dims(window, axis=0)
        
        # LSTM 예측
        prediction = ModelLoader.lstm_model.predict(window_input, verbose=0)[0]

        # 가장 높은 확률의 클래스
        predicted_idx = np.argmax(prediction)
        confidence = prediction[predicted_idx]
        
        # 신뢰도 체크
        # if confidence < 0.7:
            # logger.debug(f"   Window {i:3d}: 신뢰도 낮음 (confidence={confidence:.3f})")
            # continue
        
        # label → gloss 변환
        label = ModelLoader.label_list[predicted_idx]
        gloss = ModelLoader.gloss_dict.get(label, label)
        
        # 연속 중복 제거
        if gloss == last_gloss:
            logger.debug(f"   Window {i:3d}: 중복 제거 ({gloss})")
            continue
        
        # 글로스 추가
        gloss_seq.append(gloss)
        last_gloss = gloss
        
        logger.info(f"   Window {i:3d}: {gloss} (label={label}, confidence={confidence:.3f})")
    
    if gloss_seq:
        logger.info(f"✅ [LSTM] 예측 완료: {gloss_seq} (총 {len(gloss_seq)}개 글로스)")
    else:
        logger.warning(f"⚠️ [LSTM] 예측 결과 없음 (모든 윈도우가 신뢰도 미달)")
    
    return gloss_seq if gloss_seq else None

# ===== main =====
async def transfer_sign2gloss(data):
    """
    수어 → 글로스 → 텍스트 변환
    
    Flow:
    1. Redis에서 프레임 가져오기
    2. LSTM 모델로 글로스 시퀀스 예측
    3. LLM으로 한국어 텍스트 변환
    4. Redis 세션 정리
    """
    room_id = data.get("room_id")
    sender_id = data.get("username")
    
    try:
        # 1. Redis에서 프레임 가져오기
        logger.info(f"🔍 [Start] {room_id}:{sender_id} - 프레임 로드 시작")
        
        frame_list = await get_frames(room_id, sender_id)
        
        if not frame_list:
            logger.warning(f"⚠️ [NoFrames] {room_id}:{sender_id} - 저장된 프레임 없음")
            await clear_session(room_id, sender_id)
            return {
                "status": "error",
                "message": "저장된 프레임이 없습니다."
            }
        
        logger.info(f"✅ [LoadFrames] {room_id}:{sender_id} - {len(frame_list)}개 프레임 로드됨")
        
        # 2. LSTM 모델 예측
        logger.info(f"🔮 [LSTM] {room_id}:{sender_id} - 예측 시작...")
        
        # gloss_sequence = predict_gloss(frame_list, 30)
        gloss_sequence = ["지시", "공부", "전문", "무엇"]
        
        if gloss_sequence is None or len(gloss_sequence) == 0:
            logger.warning(f"⚠️ [NoGloss] {room_id}:{sender_id} - 글로스 예측 실패")
            await clear_session(room_id, sender_id)
            return {
                "status": "error",
                "message": "인식된 수어가 없습니다. 프레임이 부족하거나 신뢰도가 낮습니다."
            }
        
        logger.info(f"✅ [LSTM] {room_id}:{sender_id} - 글로스 시퀀스: {gloss_sequence}")
        
        # 3. LLM으로 텍스트 변환
        logger.info(f"🤖 [LLM] {room_id}:{sender_id} - 텍스트 변환 시작...")
        
        korean_text = await translate_gloss2text(gloss_sequence)
        
        logger.info(f"✅ [LLM] {room_id}:{sender_id} - 번역 완료: {korean_text}")
        
        # 4. 결과 반환
        return {
            "status": "ok",
            "gloss_sequence": gloss_sequence,
            "korean_text": korean_text
        }
    
    except Exception as e:
        logger.error(f"❌ [Error] {room_id}:{sender_id} - {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "status": "error",
            "message": f"처리 중 오류 발생: {str(e)}"
        }