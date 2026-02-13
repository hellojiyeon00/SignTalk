"""인증 관련 API 엔드포인트

회원가입, 로그인, 회원정보 조회/수정/탈퇴 기능 제공
"""
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt

from app.core.database import get_db
from app.api.schemas import UserSignup, UserLogin, UserUpdate, MessageResponse, TokenResponse
from app.core.config import settings
from app.services.auth_service import AuthService

router = APIRouter()


def create_access_token(data: dict) -> str:
    """액세스 토큰 생성 (30분 유효)"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=MessageResponse)
def signup(user_data: UserSignup, db: Session = Depends(get_db)):
    """회원가입"""
    AuthService.create_user(db, user_data)
    return {"message": "가입을 환영합니다!"}


@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """로그인"""
    user = AuthService.authenticate_user(db, login_data)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 틀렸습니다."
        )

    access_token = create_access_token(data={"sub": user[0]})
    
    return {
        "message": "로그인 성공!",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user[0],
        "user_name": user[1]
    }


@router.get("/me")
def get_my_info(user_id: str, db: Session = Depends(get_db)):
    """내 프로필 정보 조회"""
    user = AuthService.get_user_info(db, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")
        
    return {
        "user_id": user[0],
        "user_name": user[1],
        "phone_number": user[2],
        "email": user[3]
    }


@router.put("/me", response_model=MessageResponse)
def update_member(data: UserUpdate, db: Session = Depends(get_db)):
    """회원정보 수정"""
    try:
        AuthService.update_user(db, data)
        return {"message": "회원정보가 수정되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수정 실패: {str(e)}")


@router.delete("/me", response_model=MessageResponse)
def delete_member(user_id: str, db: Session = Depends(get_db)):
    """회원 탈퇴 (소프트 삭제)"""
    try:
        AuthService.delete_user(db, user_id)
        return {"message": "탈퇴 처리가 완료되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"탈퇴 실패: {str(e)}")
