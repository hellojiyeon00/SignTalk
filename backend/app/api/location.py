from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import httpx
from ..core.config import settings

router = APIRouter()

class CoordinatesRequest(BaseModel):
    latitude: float
    longitude: float

class AddressResponse(BaseModel):
    address: str
    region_1depth: str  # 시/도
    region_2depth: str  # 구/군
    region_3depth: str  # 동/면/읍

@router.post("/reverse-geocode", response_model=AddressResponse)
async def reverse_geocode(coords: CoordinatesRequest):
    """
    위도/경도를 주소로 변환 (Kakao REST API 사용)
    """
    kakao_api_key = settings.KAKAO_REST_API_KEY
    
    if not kakao_api_key:
        raise HTTPException(status_code=500, detail="Kakao API key not configured")
    
    url = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
    headers = {
        "Authorization": f"KakaoAK {kakao_api_key}"
    }
    params = {
        "x": coords.longitude,  # 경도
        "y": coords.latitude,   # 위도
        "input_coord": "WGS84"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            
            # 응답 상태 코드 로깅
            print(f"Kakao API Response Status: {response.status_code}")
            
            if response.status_code != 200:
                error_body = response.text
                print(f"Kakao API Error Response: {error_body}")
                
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
                raise HTTPException(status_code=404, detail="Address not found")
            
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
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Kakao API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reverse geocode: {str(e)}")
