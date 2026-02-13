"""데이터 스키마 정의

Pydantic을 사용한 요청/응답 데이터 모델 및 유효성 검증
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


# 요청 스키마
class UserSignup(BaseModel):
    """회원가입 요청"""
    user_id: str = Field(..., description="사용자 아이디")
    password: str = Field(..., min_length=8, description="비밀번호")
    user_name: str = Field(..., description="사용자 실명")
    phone_number: str = Field(..., description="휴대폰 번호")
    email: EmailStr = Field(..., description="이메일")
    is_deaf: bool = Field(True, description="농인 여부")


class UserLogin(BaseModel):
    """로그인 요청"""
    user_id: str
    password: str


class UserUpdate(BaseModel):
    """회원정보 수정 요청"""
    user_id: str
    user_name: Optional[str] = None
    phone_number: Optional[str] = None
    password: Optional[str] = None


class RoomCreateRequest(BaseModel):
    """채팅방 생성/입장 요청"""
    my_id: str
    target_id: str


# 응답 스키마
class MessageResponse(BaseModel):
    """기본 메시지 응답"""
    message: str


class TokenResponse(BaseModel):
    """로그인 성공 응답"""
    message: str
    access_token: str
    token_type: str
    user_id: str
    user_name: str


class RoomResponse(BaseModel):
    """채팅방 정보 응답"""
    room_id: int
    message: str
