from fastapi import APIRouter, File, UploadFile, Form
import logging

from model_app.services.lstm_service import transfer_sign2gloss

# 로거 설정
logger = logging.getLogger("model-api")
logging.basicConfig(level=logging.INFO)

# 라우터 생성
router = APIRouter()

@router.post("/translate_sign2text")
async def translate_sign2text(
    file: UploadFile = File(...),
    room: str = Form(...),
    room_id: str = Form(...),
    username: str = Form(...),
    userno: str = Form(...)
):
    try:
        # 파일 내용을 메모리에 읽기
        video_bytes = await file.read()
        
        # LSTM 서비스 호출 (바이트 데이터를 직접 전달)
        result_text = await transfer_sign2gloss(video_bytes)
        
        # 테스트용 가짜 응답
        logger.info(f"🔮 모델 추론 시작: {file.filename} (User: {username})")
        result_text = "안녕하세요" # 실제 모델 결과값이 들어갈 자리
        
        return {
            "status": "success",
            "text": result_text,
            "info": f"Processed video for {username}"
        }
        
    except Exception as e:
        logger.error(f"❌ 모델 서버 추론 에러: {e}")
        return {"status": "error", "text": "추론 실패"}