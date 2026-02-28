import json
import logging
import numpy as np
import torch

from model_app.core.redis_client import get_redis
from model_app.core.config import settings
from model_app.core.model_loader import ModelLoader, DEVICE
from model_app.services.llm_service import translate_gloss2text

logger = logging.getLogger("lstm-service")
logging.basicConfig(level=logging.INFO)

# ── 서빙 파라미터 (03_train_lstm.ipynb 와 동일하게 유지) ────────
SEQUENCE_LENGTH  = 8    # 학습 시 sequence_length
CONF_THRESHOLD   = 0.7  # 윈도우 단위 최소 신뢰도
MAX_DURATION_SEC = 1.2  # 이 시간 초과 구간 제거 (준비자세/패딩 노이즈)
MIN_DURATION_SEC = 0.2  # 이 시간 미만 구간 제거 (경계 전환 노이즈)
OVERLAP_RATIO    = 0.3  # 이전 글로스와 겹침 비율이 이 값 이상이면 신뢰도 낮은 쪽 제거
FPS              = 30   # 클라이언트 전송 fps — start_sec/end_sec 계산에 사용


# ===== Redis 키 생성 =====
def frame_key(room_id, sender_id):
    return f"sign:{room_id}:{sender_id}:frames"


# ===== Redis 작업 =====
async def get_frames(room_id, sender_id):
    """Redis에 저장된 프레임 반환"""
    redis = await get_redis()
    key = frame_key(room_id, sender_id)
    frames = await redis.lrange(key, 0, -1)
    return [json.loads(f) for f in frames]


async def clear_session(room_id, sender_id):
    """Redis 세션 정리"""
    redis = await get_redis()
    key = frame_key(room_id, sender_id)
    await redis.delete(key)
    logger.info(f"🗑️ [Redis] 세션 정리 완료: {key}")

# ===== LSTM 예측 =====
def predict_gloss(frame_list, window_size=SEQUENCE_LENGTH, stride=1,
                  conf_threshold=CONF_THRESHOLD,
                  max_duration_sec=MAX_DURATION_SEC,
                  min_duration_sec=MIN_DURATION_SEC,
                  overlap_ratio=OVERLAP_RATIO,
                  fps=FPS):
    """
    슬라이딩 윈도우 기법으로 글로스 시퀀스 예측.
    03_train_lstm.ipynb 의 extract_glosses_from_video() 와 동일한 후처리 적용.

    후처리 파이프라인:
        [1] conf_threshold 미만 윈도우 제거
        [2] 연속 중복 병합
        [3] max_duration_sec 초과 구간 제거  ← 준비자세/패딩 노이즈
        [4] 겹침(overlap) 제거              ← 경계 전환 노이즈
        [5] min_duration_sec 미만 구간 제거
    """
    # ── 모델 / 레이블 확인 ─────────────────────────────────────
    if ModelLoader.lstm_model is None:
        logger.error("❌ [LSTM] 모델이 로드되지 않음")
        return None
    if not ModelLoader.le_classes:
        logger.error("❌ [LSTM] 레이블(le_classes)이 로드되지 않음")
        return None

    # ── frame_list → numpy 변환 ─────────────────────────────────
    try:
        frames_np = np.array(frame_list, dtype=np.float32)  # (T, feat_dim)
        logger.info(f"[DEBUG] frames_np.shape: {frames_np.shape}")
    except Exception as e:
        logger.error(f"❌ [LSTM] 프레임 numpy 변환 실패: {e}")
        return None

    n = len(frames_np)
    if n < window_size:
        logger.warning(f"⚠️ [LSTM] 프레임 부족: {n} < {window_size}")
        return None

    logger.info(f"🔮 [LSTM] 슬라이딩 윈도우 시작 (총 {n}프레임, 윈도우={window_size}, stride={stride})")

    # ── 슬라이딩 윈도우 구성 ────────────────────────────────────
    starts = list(range(0, n - window_size + 1, stride))
    if starts and starts[-1] + window_size - 1 < n - 1:
        starts.append(n - window_size)

    # ── 윈도우별 추론 ────────────────────────────────────────────
    raw_results = []

    for i in starts:
        window_np     = frames_np[i: i + window_size]
        window_tensor = torch.tensor(window_np, dtype=torch.float32).unsqueeze(0).to(DEVICE)

        with torch.no_grad():
            logits = ModelLoader.lstm_model(window_tensor)
            probs  = torch.softmax(logits, dim=-1).squeeze(0).cpu().numpy()

        predicted_idx = int(np.argmax(probs))
        confidence    = float(probs[predicted_idx])

        # ── 핵심 수정: le_classes 사용 ──────────────────────────
        # label_list(CSV 읽기 순서)가 아닌 체크포인트에 저장된
        # LabelEncoder.classes_(알파벳 정렬 순서)를 사용해야
        # 학습 시 인덱스와 서빙 시 인덱스가 일치함
        label = ModelLoader.le_classes[predicted_idx]
        gloss = ModelLoader.gloss_dict.get(label, label)

        raw_results.append({
            "gloss":     gloss,
            "label":     label,
            "prob":      confidence,
            "start_sec": round(i / fps, 2),
            "end_sec":   round((i + window_size - 1) / fps, 2),
        })

    # ── [1] conf_threshold 미만 제거 ────────────────────────────
    filtered = [r for r in raw_results if r["prob"] >= conf_threshold]
    logger.info(f"[1] 신뢰도 {conf_threshold:.0%} 이상: {len(filtered)}/{len(raw_results)}개")
    if not filtered:
        logger.warning("⚠️ [LSTM] 신뢰도 통과 윈도우 없음")
        return None

    # ── [2] 연속 중복 병합 ───────────────────────────────────────
    merged = [dict(filtered[0])]
    for cur in filtered[1:]:
        if cur["gloss"] == merged[-1]["gloss"]:
            merged[-1]["end_sec"] = cur["end_sec"]
            if cur["prob"] > merged[-1]["prob"]:
                merged[-1]["prob"] = cur["prob"]
        else:
            merged.append(dict(cur))
    logger.info(f"[2] 중복 병합 후: {len(merged)}개")

    # ── [3] max_duration 초과 제거 ───────────────────────────────
    after_max = [g for g in merged if (g["end_sec"] - g["start_sec"]) <= max_duration_sec]
    logger.info(f"[3] max_duration({max_duration_sec}s) 필터 후: {len(after_max)}개")

    # ── [4] 겹침 제거 ────────────────────────────────────────────
    if after_max:
        deoverlapped = [after_max[0]]
        for cur in after_max[1:]:
            prev    = deoverlapped[-1]
            overlap = prev["end_sec"] - cur["start_sec"]
            cur_dur = cur["end_sec"] - cur["start_sec"]
            if overlap > 0 and cur_dur > 0 and (overlap / cur_dur) >= overlap_ratio:
                if cur["prob"] > prev["prob"]:
                    deoverlapped[-1] = cur
            else:
                deoverlapped.append(cur)
    else:
        deoverlapped = []
    logger.info(f"[4] 겹침 제거 후: {len(deoverlapped)}개")

    # ── [5] min_duration 미만 제거 ───────────────────────────────
    final = [g for g in deoverlapped if (g["end_sec"] - g["start_sec"]) >= min_duration_sec]
    logger.info(f"[5] min_duration({min_duration_sec}s) 필터 후: {len(final)}개")

    gloss_seq = [g["gloss"] for g in final]

    if gloss_seq:
        logger.info(f"✅ [LSTM] 예측 완료: {gloss_seq}")
        for g in final:
            logger.info(
                f"   {g['gloss']:<15} label={g['label']}  "
                f"prob={g['prob']:.3f}  "
                f"{g['start_sec']}s ~ {g['end_sec']}s"
            )
    else:
        logger.warning("⚠️ [LSTM] 최종 결과 없음 (모든 구간이 필터링됨)")

    return gloss_seq if gloss_seq else None


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