"""재난문자 테스트 라우터 (DEBUG 모드 전용)

실제 Kafka를 거치지 않고 SSE 큐에 직접 모의 재난문자를 주입합니다.
.env에 DEBUG=true일 때만 main.py에서 등록됩니다.
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from app.api.auth import verify_token
from app.services.disaster_service import connected_clients

router = APIRouter()
logger = logging.getLogger("test_disaster")


@router.post("/broadcast", summary="모의 재난문자 브로드캐스트 (테스트용)")
async def test_broadcast(current_user_id: str = Depends(verify_token)):
    """현재 SSE에 연결된 모든 클라이언트에게 모의 재난문자를 전송합니다.

    사용 방법:
    1. 브라우저에서 채팅 화면을 열어 SSE 연결 유지
    2. http://localhost:8000/docs → POST /disaster/test/broadcast → Execute
    """
    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST).strftime("%H:%M")

    disaster_data = {
        "id": str(int(datetime.now().timestamp())),
        "message": "🚨 [테스트] 이것은 재난문자 수신 테스트입니다. 실제 재난 상황이 아닙니다.",
        "type_code": "SA",
        "type_name": "안전안내",
        "disaster_type": "테스트",
        "region": "전국",
        "time": now_kst,
    }

    if not connected_clients:
        return {
            "status": "no_clients",
            "message": "현재 SSE에 연결된 클라이언트가 없습니다. 브라우저에서 채팅 화면을 열어두세요.",
        }

    for client_queue in list(connected_clients.values()):
        try:
            await client_queue.put(disaster_data)
        except Exception as e:
            logger.error(f"브로드캐스트 오류: {e}")

    logger.info(f"🧪 [테스트] 재난문자 브로드캐스트 → {len(connected_clients)}명")
    return {
        "status": "ok",
        "sent_to": len(connected_clients),
        "clients": list(connected_clients.keys()),
        "data": disaster_data,
    }
