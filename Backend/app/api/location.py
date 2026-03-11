"""위치 API 라우터

GPS 좌표를 주소로 변환하는 역지오코딩 엔드포인트
"""
from fastapi import APIRouter, Depends
from app.api.schemas import CoordinatesRequest, AddressResponse
from app.services.location_service import LocationService
from app.api.auth import verify_token

router = APIRouter()

@router.post("/reverse-geocode", response_model=AddressResponse)
async def reverse_geocode(
    coords: CoordinatesRequest,
    current_user_id: str = Depends(verify_token)
):
    """위도/경도를 주소로 변환 (JWT 토큰 필수)
    
    Args:
        coords: 위도/경도 정보
        current_user_id: JWT 토큰에서 추출한 사용자 ID
        
    Returns:
        AddressResponse: 주소 및 행정구역 정보
    """
    return await LocationService.reverse_geocode(
        latitude=coords.latitude,
        longitude=coords.longitude
    )
