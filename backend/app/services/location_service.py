"""위치 서비스

Kakao Map API를 사용한 역지오코딩 비즈니스 로직
"""
import logging

import httpx
from fastapi import HTTPException
from app.core.config import settings
from app.api.schemas import AddressResponse

logger = logging.getLogger(__name__)


class LocationService:
    """위치 관련 비즈니스 로직 처리"""

    @staticmethod
    async def reverse_geocode(latitude: float, longitude: float) -> AddressResponse:
        """위도/경도를 주소로 변환 (Kakao REST API 사용)
        
        Args:
            latitude: 위도
            longitude: 경도
            
        Returns:
            AddressResponse: 주소 및 행정구역 정보
            
        Raises:
            HTTPException: API 키 미설정, 지도 API 비활성화, 주소 없음
        """
        kakao_api_key = settings.KAKAO_REST_API_KEY
        
        if not kakao_api_key:
            raise HTTPException(
                status_code=500, 
                detail="Kakao API key not configured"
            )
        
        # Kakao API URL (환경 변수에서 로드)
        url = settings.KAKAO_API_URL
        headers = {
            "Authorization": f"KakaoAK {kakao_api_key}"
        }
        params = {
            "x": longitude,  # 경도
            "y": latitude,   # 위도
            "input_coord": "WGS84"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code != 200:
                    error_body = response.text
                    logger.error(f"Kakao API 오류 [{response.status_code}]: {error_body}")
                    
                    # 403 오류 시 친절한 메시지
                    if response.status_code == 403:
                        raise HTTPException(
                            status_code=503,
                            detail="Kakao Map API가 활성화되지 않았습니다. Kakao Developers 콘솔에서 '제품 설정 → 지도'를 활성화해주세요."
                        )
                    
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Kakao API error: {error_body}"
                    )
                
                data = response.json()
                
                if not data.get("documents"):
                    raise HTTPException(
                        status_code=404, 
                        detail="Address not found"
                    )
                
                # 도로명 주소 우선, 없으면 지번 주소 사용
                document = data["documents"][0]
                
                if document.get("road_address"):
                    road = document["road_address"]
                    address = road["address_name"]
                    region_1depth = road["region_1depth_name"]
                    region_2depth = road["region_2depth_name"]
                    region_3depth = road["region_3depth_name"]
                else:
                    addr = document["address"]
                    address = addr["address_name"]
                    region_1depth = addr["region_1depth_name"]
                    region_2depth = addr["region_2depth_name"]
                    region_3depth = addr["region_3depth_name"]
                
                return AddressResponse(
                    address=address,
                    region_1depth=region_1depth,
                    region_2depth=region_2depth,
                    region_3depth=region_3depth
                )
        
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to reverse geocode: {str(e)}"
            )
