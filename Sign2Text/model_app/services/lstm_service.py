import cv2
import mediapipe as mp
import numpy as np
import tensorflow as tf
import os
import io
import tempfile
import asyncio

from model_app.core.redis_client import get_redis
from model_app.core.config import settings
from model_app.core.model_loader import ModelLoader
from model_app.services.llm_service import translate_gloss2text

logger = logging.getLogger("lstm-service")
logging.basicConfig(level=logging.INFO)

# 환경 설정 및 리소스 로드
mp_holistic = mp.solutions.holistic

# 학습 때 사용한 설정값
POSE_LANDMARKS = [11, 12, 13, 14, 15, 16]
HAND_LANDMARKS = [i for i in range(21)]
sequence_length = 45  
threshold = 0.8

# 랜드마크 추출
def extract_landmarks(results):
    def get_coord(landmarks, idx):
        if landmarks is None:
            return np.zeros(len(idx) * 2)
        coord_list = []
        for i in idx:
            lm = landmarks.landmark[i]
            coord_list.extend([lm.x, lm.y])
        return np.array(coord_list)

    pose_coord = get_coord(results.pose_landmarks, POSE_LANDMARKS)
    left_hand_coord = get_coord(results.left_hand_landmarks, HAND_LANDMARKS)
    right_hand_coord = get_coord(results.right_hand_landmarks, HAND_LANDMARKS)
    
    return np.concatenate([pose_coord, left_hand_coord, right_hand_coord])

# ===== LSTM 예측 =====
def predict_gloss(frame_list):
    """
    슬라이딩 윈도우 기법으로 글로스 시퀀스 예측.
    """
    # 모델 / 레이블 확인
    if ModelLoader.lstm_model is None:
        logger.error("❌ [LSTM] 모델이 로드되지 않음")
        return None
    if not ModelLoader.label_list:
        logger.error("❌ [LSTM] 레이블(label_list)이 로드되지 않음")
        return None

    # frame_list → numpy 변환
    try:
        frames_np = np.array(frame_list, dtype=np.float32)  # (T, feat_dim)
        logger.info(f"[DEBUG] frames_np.shape: {frames_np.shape}")
    except Exception as e:
        logger.error(f"❌ [LSTM] 프레임 numpy 변환 실패: {e}")
        return None

    n = len(frames_np)
    if n < WINDOW_SIZE:
        logger.warning(f"⚠️ [LSTM] 프레임 부족: {n} < {WINDOW_SIZE}")
        return None

    logger.info(f"🔮 [LSTM] 슬라이딩 윈도우 시작 (총 {n}프레임, 윈도우={WINDOW_SIZE}, stride={STRIDE})")

    # 슬라이딩 윈도우 구성
    starts = list(range(0, n - WINDOW_SIZE + 1, STRIDE))
    if starts and starts[-1] + WINDOW_SIZE - 1 < n - 1:
        starts.append(n - WINDOW_SIZE)

    # 윈도우별 추론
    raw_results = []

    for i in starts:
        window_np = frames_np[i: i + WINDOW_SIZE]
        res_input = np.expand_dims(window_np, axis=0)

        # TF 모델 예측
        res = ModelLoader.lstm_model.predict(res_input, verbose=0)[0]

        predicted_idx = np.argmax(res)
        confidence = float(res[predicted_idx])

        # 임계값 필터링
        if confidence > CONF_THRESHOLD:
            # ModelLoader.all_labels는 학습 시 클래스 순서 리스트
            label = ModelLoader.label_list[predicted_idx]
            gloss = ModelLoader.gloss_dict.get(label, label)

        raw_results.append({
            "gloss":     gloss,
            "label":     label,
            "prob":      confidence,
            "start_sec": round(i / FPS, 2),
            "end_sec":   round((i + WINDOW_SIZE - 1) / FPS, 2),
        })

        logger.info(f"predicted gloss: {gloss}")

    # 중복 제거 및 시퀀스 정제
    final_glosses = [r['gloss'] for r in raw_results]
    
    # 연속으로 중복되는 단어 제거 (예: ['안녕', '안녕', '학교'] -> ['안녕', '학교'])
    result_sequence = []
    if final_glosses:
        result_sequence.append(final_glosses[0])
        for j in range(1, len(final_glosses)):
            if final_glosses[j] != final_glosses[j-1]:
                result_sequence.append(final_glosses[j])
                
    return result_sequence

# ===== main =====
async def transfer_sign2gloss(data):
    """수어 → 글로스 → 텍스트 변환"""
    room_id   = data.get("room_id")
    sender_id = data.get("username")

    try:
        # 1. Redis에서 프레임 가져오기
        logger.info(f"🔍 [Start] {room_id}:{sender_id} - 프레임 로드 시작")
        frame_list = await get_frames(room_id, sender_id)

        if not frame_list:
            logger.warning(f"⚠️ [NoFrames] {room_id}:{sender_id} - 저장된 프레임 없음")
            return {"status": "error", "message": "저장된 프레임이 없습니다."}

        logger.info(f"✅ [LoadFrames] {room_id}:{sender_id} - {len(frame_list)}개 프레임 로드됨")

        # 2. LSTM 예측
        logger.info(f"🔮 [LSTM] {room_id}:{sender_id} - 예측 시작...")
        gloss_sequence = predict_gloss(frame_list)

        if not gloss_sequence:
            logger.warning(f"⚠️ [NoGloss] {room_id}:{sender_id} - 글로스 예측 실패")
            return {
                "status": "error",
                "message": "인식된 수어가 없습니다. 프레임이 부족하거나 신뢰도가 낮습니다."
            }

        logger.info(f"✅ [LSTM] {room_id}:{sender_id} - 글로스 시퀀스: {gloss_sequence}")

        # 3. LLM 텍스트 변환
        logger.info(f"🤖 [LLM] {room_id}:{sender_id} - 텍스트 변환 시작...")
        korean_text = await translate_gloss2text(gloss_sequence)
        logger.info(f"✅ [LLM] {room_id}:{sender_id} - 번역 완료: {korean_text}")

        return {
            "status": "ok",
            "gloss_sequence": gloss_sequence,
            "korean_text": korean_text
        }

    except Exception as e:
        logger.error(f"❌ [Error] {room_id}:{sender_id} - {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"처리 중 오류 발생: {str(e)}"}