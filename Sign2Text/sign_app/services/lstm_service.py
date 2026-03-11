import cv2
import numpy as np
import os
import tempfile
import logging
from sign_app.core.model_loader import ModelLoader

logger = logging.getLogger("lstm-service")
logging.basicConfig(level=logging.INFO)

# 설정값 (학습 시와 동일하게 세팅)
POSE_LANDMARKS = [11, 12, 13, 14, 15, 16]
HAND_LANDMARKS = [i for i in range(21)]
WINDOW_SIZE = 45  
THRESHOLD = 0.8

def extract_landmarks(results):
    """MediaPipe 결과에서 특정 랜드마크 좌표 추출"""
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

async def transfer_sign2gloss(video_bytes: bytes):
    """
    영상을 분석하여 연속 중복이 제거된 단어 시퀀스를 반환합니다.
    """
    # 전역 ModelLoader에서 리소스 가져오기
    model = ModelLoader.lstm_model
    label_list = ModelLoader.label_list
    gloss_dict = ModelLoader.gloss_dict
    holistic = ModelLoader.mp_holistic

    logger.info("모델 불러오기 완료")

    # 임시 파일 생성
    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
        temp_file.write(video_bytes)
        temp_path = temp_file.name

    sequence = []
    raw_results = [] 

    try:
        cap = cv2.VideoCapture(temp_path)
        fps = cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 30
        frame_idx = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break

            # 전처리 및 MediaPipe 추론
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = holistic.process(image_rgb)
                
            # 랜드마크 추출 및 시퀀스 축적
            keypoints = extract_landmarks(results)
            sequence.append(keypoints)
            sequence = sequence[-WINDOW_SIZE:]

            # 윈도우 사이즈가 채워졌을 때 예측 수행
            if len(sequence) == WINDOW_SIZE:
                res_input = np.expand_dims(sequence, axis=0)
                # 추론 속도 향상을 위해 verbose=0 설정
                res = model.predict(res_input, verbose=0)[0]
                    
                idx = np.argmax(res)
                confidence = res[idx]

                if confidence > THRESHOLD:
                    # 라벨 리스트에서 라벨 추출
                    label = label_list[idx]
                    # gloss_dict에서 라벨 값으로 글로스 반환 (없으면 라벨 사용)
                    glosses = gloss_dict.get(label, label) if gloss_dict else label
                    word = glosses.split(",")[0]
                    
                    raw_results.append({
                        "gloss": word,
                        "prob": float(confidence),
                        "frame": frame_idx
                    })
                    logger.info(f"Frame {frame_idx} | Predicted: {word} ({confidence:.2f})")

            frame_idx += 1

        cap.release()

        # --- 중복 제거 및 시퀀스 정제 로직 ---
        # 1. raw_results에서 단어 리스트만 추출
        predicted_glosses = [r['gloss'] for r in raw_results]
        
        # 2. 연속으로 중복되는 단어 제거
        result_sequence = []
        if predicted_glosses:
            result_sequence.append(predicted_glosses[0])
            for j in range(1, len(predicted_glosses)):
                # 이전 프레임의 단어와 다를 때만 리스트에 추가
                if predicted_glosses[j] != predicted_glosses[j-1]:
                    result_sequence.append(predicted_glosses[j])

        # 3. 최종 결과 반환
        if not result_sequence:
            return "인식된 수어가 없습니다."
            
        return " ".join(result_sequence)

    except Exception as e:
        logger.error(f"Error in transfer_sign2gloss: {e}")
        return f"번역 오류 발생: {str(e)}"
    
    finally:
        # 사용한 임시 파일 삭제
        if os.path.exists(temp_path):
            os.remove(temp_path)