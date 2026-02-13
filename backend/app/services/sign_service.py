import logging
from datetime import datetime, timedelta, timezone
from fastapi.concurrency import run_in_threadpool

# 로거 설정
logger = logging.getLogger("socket")

# 유저별로 랜드마크 버퍼(Redis를 안 쓴다면 일단 전역 변수)
user_landmarks_buffers = {}
# 유저별 단어 버퍼(Redis를 안 쓴다면 일단 전역 변수)
user_gloss_buffers = {}

gloss_dict = {i: f"단어 {i}" for i in range(100)}

# 글로스 -> 문장 변환(LLM API 사용)
async def transfer_gloss2text(gloss_list):
    """
    유저별 gloss_list를 LLM에 입력하여 문장 생성 및 반환
    """
    text = " ".join(gloss_list)
    return text

# 랜드마크 -> 글로스 변환(LSTM 모델 사용)
async def transfer_sign2gloss(data):
    """
    전달받은 landmarks를 모델에 넣고 gloss 반환
    """
    room_id = data.get("room_id")
    room_name = data.get("room")
    sender_id = data.get("username")
    landmarks = data.get("message")
    status = data.get("stopBtn") # True: 전송 종료, False: 전송 중

    # 종료 버튼(stopBtn) 눌렀을 때
    if status:
        gloss_list = user_gloss_buffers[sender_id]
        print(gloss_list)
        if not gloss_list:
            print("인식된 단어가 없습니다.")
        msg = await transfer_gloss2text(user_gloss_buffers[sender_id])
        print(f"반환된 문장: {msg}")

        # 해당 유저의 저장소 초기화
        user_landmarks_buffers[sender_id] = []
        user_gloss_buffers[sender_id] = []

        return msg
    
    # 유저 저장소 초기화
    if sender_id not in user_landmarks_buffers:
        user_landmarks_buffers[sender_id] = []
    if sender_id not in user_gloss_buffers:
        user_gloss_buffers[sender_id] = []

    user_landmarks_buffers[sender_id].append(landmarks)
    predicted_gloss = None

    # [여기에 AI 모델 예측 로직 삽입]
    # 예시 테스트용: 10프레임마다 가짜 단어 생성
    if len(user_landmarks_buffers[sender_id]) % 10 == 0:
        num = len(user_landmarks_buffers[sender_id]) // 10
        predicted_gloss = gloss_dict[num]
        print(predicted_gloss)
    
    if predicted_gloss:
        user_gloss_buffers[sender_id].append(predicted_gloss)