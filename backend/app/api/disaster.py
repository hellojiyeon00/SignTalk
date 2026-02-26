"""재난문자 SSE 스트리밍 API

Server-Sent Events를 사용한 실시간 재난문자 전송
"""
import json
import logging
from fastapi import APIRouter, Request, Depends
from sse_starlette.sse import EventSourceResponse

from app.services.disaster_service import DisasterService
from app.api.auth import verify_token

# 단방향 통신을 위한 SSE 라우터 생성(Socket.IO은 양방향 통신이므로 별도의 라우터로 분리) 

router = APIRouter()
# 로거 설정(로거 이름은 "disaster_api"로 설정하여 재난문자 API 관련 로그를 구분)
logger = logging.getLogger("disaster_api")


# @router.get("/stream"): GET 요청으로 SSE 스트림 제공 (JWT 인증 필수)
@router.get("/stream")
async def disaster_stream(
    request: Request,
    current_user_id: str = Depends(verify_token)
):
    """SSE 스트림 엔드포인트 (JWT 토큰 필수)
    
    클라이언트가 이 엔드포인트에 연결하면 실시간으로 재난문자를 수신합니다.
    fetch 기반 SSE를 사용하여 JWT 인증 지원
    
    Args:
        request: FastAPI Request 객체
        current_user_id: JWT 토큰에서 추출한 사용자 ID
    
    Returns:
        EventSourceResponse: SSE 스트림
    """
    
    # 데이터를 생성하는 비동기 제너레이터 함수 정의
    async def event_generator():
        """SSE 이벤트 생성기 래퍼"""
        
        # 재난문자 스트림 생성기에서 이벤트를 비동기로 읽어와서 클라이언트로 전송
        async for event in DisasterService.generate_disaster_stream(current_user_id, request):
            # 데이터를 JSON 문자열로 변환
            if "data" in event and isinstance(event["data"], dict):
                event["data"] = json.dumps(event["data"])
                
            # return 대신 yield 사용(return은 함수 종료, yield는 이벤트를 하나씩 생성하여 스트림 유지)
            yield event
    
    return EventSourceResponse(event_generator())

