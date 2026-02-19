"""재난문자 SSE 스트리밍 API

Server-Sent Events를 사용한 실시간 재난문자 전송
"""
import json
import logging
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.services.disaster_service import DisasterService

router = APIRouter()
logger = logging.getLogger("disaster_api")


@router.get("/stream")
async def disaster_stream(request: Request, user_id: str):
    """SSE 스트림 엔드포인트
    
    클라이언트가 이 엔드포인트에 연결하면 실시간으로 재난문자를 수신합니다.
    나중에 위치 기반 필터링을 추가할 예정입니다.
    
    Args:
        user_id: 사용자 ID (나중에 위치 필터링에 사용)
        request: FastAPI Request 객체
    
    Returns:
        EventSourceResponse: SSE 스트림
    """
    
    async def event_generator():
        """SSE 이벤트 생성기 래퍼"""
        async for event in DisasterService.generate_disaster_stream(user_id, request):
            # 데이터를 JSON 문자열로 변환
            if "data" in event and isinstance(event["data"], dict):
                event["data"] = json.dumps(event["data"])
            yield event
    
    return EventSourceResponse(event_generator())

