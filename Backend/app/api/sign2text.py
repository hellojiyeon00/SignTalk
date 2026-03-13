import os
import httpx
import logging
from dotenv import load_dotenv
from fastapi import APIRouter, File, UploadFile, Form, HTTPException

# 로거 설정
logger = logging.getLogger("sign2text_api")
logging.basicConfig(level=logging.INFO)

# 라우터 생성
router = APIRouter()

# .env 파일 로드
load_dotenv()

SIGN_BASE_URL = os.getenv("SIGN_BASE_URL")

@router.post("/save_video")
async def save_video(
    file: UploadFile = File(...),
    room: str = Form(...),
    room_id: str = Form(...),
    username: str = Form(...),
    userno: str = Form(...)
):
    # 전송 확인용 로그
    print(f"📥 영상 수신 테스트: 유저 {username}, 방 {room_id}")
    print(f"📹 파일명: {file.filename}, 컨텐츠 타입: {file.content_type}")
    
    # 모델 서버로 영상 전송 (저장 X)
    try:
        file_content = await file.read()
        
        # verify=False : 비동기 HTTP 클라이언트 생성 시 SSL/TLS 인증서 검증을 비활성화
        # 메인 서버에서 자가 서명 인증서(Self-signed certificate) 사용 중 
        async with httpx.AsyncClient(verify=False) as client:
            files = {'file': (file.filename, file_content, file.content_type)}
            data = {'room': room, 'room_id': room_id, 'username': username, 'userno': userno}
            
            response = await client.post(f"{SIGN_BASE_URL}/model/translate_sign2text", files=files, data=data, timeout=60.0)
            
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="모델 서버 응답 오류")

        result = response.json()
        
        return {
            "status": "success",
            "message": result.get("text", "번역 결과 없음")
        }

    except Exception as e:
        logger.error(f"❌ 중계 처리 실패: {e}")
        raise HTTPException(status_code=500, detail="영상 처리 중 오류 발생")