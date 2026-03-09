"""재난문자 테스트 라우터 (DEBUG 모드 전용)

실제 Kafka를 거치지 않고 SSE 큐에 직접 모의 재난문자를 주입합니다.
.env에 DEBUG=true일 때만 main.py에서 등록됩니다.
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.services.disaster_service import connected_clients

router = APIRouter()
logger = logging.getLogger("test_disaster")


DISASTER_PRESETS = {
    "SA": {
        "type_code": "SA",
        "type_name": "안전안내",
        "message": "🔵 [테스트] 안전안내 문자입니다. 실제 재난 상황이 아닙니다.",
    },
    "EM": {
        "type_code": "EM",
        "type_name": "긴급재난",
        "message": "🟠 [테스트] 긴급재난 문자입니다. 실제 재난 상황이 아닙니다.",
    },
    "EX": {
        "type_code": "EX",
        "type_name": "위급재난",
        "message": "🔴 [테스트] 위급재난 문자입니다. 실제 재난 상황이 아닙니다.",
    },
}


async def _broadcast(disaster_data: dict) -> dict:
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


def _make_data(preset: dict) -> dict:
    KST = timezone(timedelta(hours=9))
    return {
        "id": str(int(datetime.now().timestamp())),
        "message": preset["message"],
        "type_code": preset["type_code"],
        "type_name": preset["type_name"],
        "disaster_type": "테스트",
        "region": "전국",
        "time": datetime.now(KST).strftime("%H:%M"),
    }


@router.post("/broadcast", summary="모의 재난문자 브로드캐스트 - 안전안내 SA (테스트용)")
async def test_broadcast_sa():
    """안전안내(SA) 모의 재난문자를 전송합니다."""
    return await _broadcast(_make_data(DISASTER_PRESETS["SA"]))


@router.post("/broadcast/em", summary="모의 재난문자 브로드캐스트 - 긴급재난 EM (테스트용)")
async def test_broadcast_em():
    """긴급재난(EM) 모의 재난문자를 전송합니다."""
    return await _broadcast(_make_data(DISASTER_PRESETS["EM"]))


@router.post("/broadcast/ex", summary="모의 재난문자 브로드캐스트 - 위급재난 EX (테스트용)")
async def test_broadcast_ex():
    """위급재난(EX) 모의 재난문자를 전송합니다."""
    return await _broadcast(_make_data(DISASTER_PRESETS["EX"]))
