from fastapi import APIRouter, File, UploadFile, Form
import logging

from model_app.services.lstm_service import transfer_sign2gloss
from model_app.services.llm_service import transfer_gloss2text

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
        gloss_sequence = await transfer_sign2gloss(video_bytes)
        
        # LLM API 호출
        text = await transfer_gloss2text(gloss_sequence)

        if text is None:
            text = gloss_sequence
        
        return {
            "status": "success",
            "text": text,
            "info": f"Processed video for {username}"
        }
        
    except Exception as e:
        logger.error(f"❌ 모델 서버 추론 에러: {e}")
        return {"status": "error", "text": "추론 실패"}