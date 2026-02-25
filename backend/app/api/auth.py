"""인증 관련 API 엔드포인트

회원가입, 로그인, 회원정보 조회/수정/탈퇴 기능 제공
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt, JWTError

from app.core.database import get_db
from app.api.schemas import UserSignup, UserLogin, UserUpdate, MessageResponse, TokenResponse
from app.core.config import settings
from app.services.auth_service import AuthService

# 인증 API 라우터 생성
router = APIRouter()

# HTTP Bearer 인증 스킴 (Authorization: Bearer <token>)
security = HTTPBearer()


# JWT 토큰 검증 함수 (의존성 주입용)
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """JWT 토큰을 검증하고 user_id를 반환합니다.
    
    Args:
        credentials: HTTP Authorization 헤더의 Bearer 토큰
        
    Returns:
        str: 토큰에서 추출한 user_id
        
    Raises:
        HTTPException: 토큰이 유효하지 않거나 만료된 경우
    """
    try:
        # 1. 토큰 디코딩 (서명 검증 + 만료 시간 확인)
        payload = jwt.decode(
            credentials.credentials, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        # 2. 토큰에서 user_id 추출 (subject)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 토큰입니다.",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return user_id
        
    except JWTError as e:
        # 토큰 만료, 서명 불일치, 형식 오류 등
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증에 실패했습니다. 다시 로그인해주세요.",
            headers={"WWW-Authenticate": "Bearer"}
        )


# JWT 토큰 생성 함수(로그인 유지를 위한 액세스 토큰)
def create_access_token(data: dict) -> str:
    """액세스 토큰 생성 (30분 유효)"""
    
    # 1. 토큰에 담을 데이터(유저 정보) 복사
    to_encode = data.copy() 
    
    # 2. 만료 시간 설정
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    
    # 3. JWT 토큰 생성
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# HTTP 메서드 설명
# POST: 웹 서버로 데이터 전송
# GET: 웹 서버에서 데이터 조회
# PUT: 웹 서버의 데이터 전체 수정
# DELETE: 웹 서버의 데이터 삭제
# PATCH: 웹 서버의 데이터 일부 수정

# @router.post("/signup"): POST로 요청하면 회원가입 처리
# status_code=status.HTTP_201_CREATED: 성공 시 201 Created 상태 코드 반환
@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=MessageResponse)
def signup(user_data: UserSignup, db: Session = Depends(get_db)):
    """회원가입"""
    
    # 회원가입 처리 - auth_service에 있는 AuthService의 create_user 메서드 호출
    AuthService.create_user(db, user_data)
    return {"message": "가입을 환영합니다!"}


# @router.post("/login"): POST로 요청하면 로그인 처리
# response_model=TokenResponse: 로그인 성공 시 schemas에 정의된 액세스 토큰과 사용자 정보를 반환
@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """로그인"""
    
    # 사용자 인증 - auth_service에 있는 AuthService의 authenticate_user 메서드 호출
    user = AuthService.authenticate_user(db, login_data)
    
    # 사용자 인증 실패 시 401 Unauthorized 예외 발생
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 틀렸습니다."
        )

    # 사용자 인증 성공 시 JWT 액세스 토큰 생성 (user[0]: user_id)
    access_token = create_access_token(data={"sub": user[0]})
    
    # 로그인 성공 시 토큰과 사용자 정보를 반환
    return {
        "message": "로그인 성공!",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user[0],
        "user_name": user[1]
    }


# @router.get("/me"): GET으로 요청하면 내 프로필 정보 조회 (JWT 인증 필수)
@router.get("/me")
def get_my_info(
    current_user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """내 프로필 정보 조회 (JWT 토큰 필수)"""
    
    # JWT 토큰에서 추출한 user_id로 사용자 정보 조회
    user = AuthService.get_user_info(db, current_user_id)
    
    # 사용자 정보가 없으면 404 Not Found 예외 발생
    if not user:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")
    
    # 사용자 정보 반환 (user[0]: user_id, user[1]: user_name, user[2]: phone_number, user[3]: email)
    return {
        "user_id": user[0],
        "user_name": user[1],
        "phone_number": user[2],
        "email": user[3]
    }


# @router.put("/me"): PUT으로 요청하면 내 프로필 정보 수정 (JWT 인증 필수)
@router.put("/me", response_model=MessageResponse)
def update_member(
    data: UserUpdate,
    current_user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """회원정보 수정 (JWT 토큰 필수)"""
    
    # 토큰의 user_id와 요청 데이터의 user_id가 일치하는지 확인
    if data.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 정보만 수정할 수 있습니다."
        )
    
    try:
        # 회원정보 수정 - auth_service에 있는 AuthService의 update_user 메서드 호출
        AuthService.update_user(db, data)
        return {"message": "회원정보가 수정되었습니다."}
    except Exception as e:
        # 수정 실패 시 500 Internal Server Error 예외 발생
        raise HTTPException(status_code=500, detail="회원정보 수정에 실패했습니다.")


# @router.delete("/me"): DELETE로 요청하면 회원 탈퇴 처리 (소프트 삭제, JWT 인증 필수)
@router.delete("/me", response_model=MessageResponse)
def delete_member(
    current_user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """회원 탈퇴 (소프트 삭제, JWT 토큰 필수)"""
    
    try:
        # JWT 토큰에서 추출한 user_id로 회원 탈퇴 처리
        AuthService.delete_user(db, current_user_id)
        return {"message": "탈퇴 처리가 완료되었습니다."}
    except Exception as e:
        # 탈퇴 실패 시 500 Internal Server Error 예외 발생
        raise HTTPException(status_code=500, detail="회원 탈퇴 처리에 실패했습니다.")
