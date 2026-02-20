"""위치 API 라우터

GPS 좌표를 주소로 변환하는 역지오코딩 엔드포인트
"""
from fastapi import APIRouter
from app.api.schemas import CoordinatesRequest, AddressResponse
from app.services.location_service import LocationService

router = APIRouter()

@router.post("/reverse-geocode", response_model=AddressResponse)
async def reverse_geocode(coords: CoordinatesRequest):
    """위도/경도를 주소로 변환
    
    Args:
        coords: 위도/경도 정보
        
    Returns:
        AddressResponse: 주소 및 행정구역 정보
    """
    return await LocationService.reverse_geocode(
        latitude=coords.latitude,
        longitude=coords.longitude
    )
