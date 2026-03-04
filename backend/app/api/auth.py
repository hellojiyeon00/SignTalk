"""인증 관련 API 엔드포인트

회원가입, 로그인, 회원정보 조회/수정/탈퇴 기능 제공
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt, JWTError

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.api.schemas import (
    UserSignup, UserLogin, UserUpdate, MessageResponse,
    TokenResponse, RefreshTokenRequest,
    EmailVerifyRequest, EmailCodeVerifyRequest,
    PasswordResetSendRequest, PasswordResetRequest,
)
from app.core.config import settings
from app.services.auth_service import AuthService
from app.services.email_service import send_verification_email

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
    to_encode.update({"exp": expire, "type": "access"})
    
    # 3. JWT 토큰 생성
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """리프레시 토큰 생성 (7일 유효)"""
    
    # 1. 토큰에 담을 데이터 복사
    to_encode = data.copy()
    
    # 2. 만료 시간 설정 (7일)
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire, "type": "refresh"})
    
    # 3. JWT 토큰 생성
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# HTTP 메서드 설명
# POST: 웹 서버로 데이터 전송
# GET: 웹 서버에서 데이터 조회
# PUT: 웹 서버의 데이터 전체 수정
# DELETE: 웹 서버의 데이터 삭제
# PATCH: 웹 서버의 데이터 일부 수정

# ─── 이메일 인증 코드 발송 ─────────────────────────────────────────
@router.post("/send-verify-email", response_model=MessageResponse)
async def send_verify_email(data: EmailVerifyRequest):
    """이메일로 6자리 인증 코드 발송 (5분 유효)"""
    redis = await get_redis()

    # 중복 가입 방지: 이미 DB에 같은 이메일이 있는지는 signup에서 처리하므로 여기선 스킵
    # 1분 이내 재요청 방지 (스팸 방지용 쿨다운)
    cooldown_key = f"email_cooldown:{data.email}"
    if await redis.get(cooldown_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="1분 후 다시 시도해주세요."
        )

    try:
        code = await send_verification_email(str(data.email))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"메일 발송 실패: {e}"
        )

    # Redis에 코드 저장 (TTL 5분)
    await redis.set(f"email_code:{data.email}", code, ex=300)
    # 쿨다운 60초 설정
    await redis.set(cooldown_key, "1", ex=60)

    return {"message": "인증 코드가 발송되었습니다."}


# ─── 이메일 인증 코드 확인 ─────────────────────────────────────────
@router.post("/verify-email-code", response_model=MessageResponse)
async def verify_email_code(data: EmailCodeVerifyRequest):
    """사용자가 입력한 인증 코드 확인"""
    redis = await get_redis()

    saved_code = await redis.get(f"email_code:{data.email}")

    if not saved_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="인증 코드가 만료되었거나 존재하지 않습니다. 다시 발송해주세요."
        )

    if saved_code != data.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="인증 코드가 일치하지 않습니다."
        )

    # 인증 완료 표시 (TTL 10분 — 이 안에 회원가입 완료해야 함)
    await redis.set(f"email_verified:{data.email}", "1", ex=600)
    # 사용한 코드 즉시 삭제 (재사용 방지)
    await redis.delete(f"email_code:{data.email}")

    return {"message": "이메일 인증이 완료되었습니다."}


# @router.post("/signup"): POST로 요청하면 회원가입 처리
# status_code=status.HTTP_201_CREATED: 성공 시 201 Created 상태 코드 반환
@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=MessageResponse)
async def signup(user_data: UserSignup, db: Session = Depends(get_db)):
    """회원가입 (이메일 인증 필수)"""
    # 이메일 인증 완료 여부 컨폭여 확인
    redis = await get_redis()
    verified = await redis.get(f"email_verified:{user_data.email}")
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이메일 인증이 필요합니다."
        )

    # 회원가입 처리
    AuthService.create_user(db, user_data)

    # 인증 토큰 삭제 (재사용 방지)
    await redis.delete(f"email_verified:{user_data.email}")

    return {"message": "가입을 환영합니다!"}


# ─── 비밀번호 재설정 코드 발송 ────────────────────────────────────────
@router.post("/send-reset-email", response_model=MessageResponse)
async def send_reset_email(data: PasswordResetSendRequest, db: Session = Depends(get_db)):
    """아이디 + 이메일 일치 확인 후 재설정 코드 발송 (5분 유효)"""
    if not AuthService.verify_user_email(db, data.user_id, str(data.email)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="아이디 또는 이메일이 일치하지 않습니다.")

    redis = await get_redis()
    cooldown_key = f"reset_cooldown:{data.email}"
    if await redis.get(cooldown_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="1분 후 다시 시도해주세요.")

    try:
        code = await send_verification_email(str(data.email))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"메일 발송 실패: {e}")

    await redis.set(f"reset_code:{data.email}", code, ex=300)
    await redis.set(cooldown_key, "1", ex=60)
    return {"message": "인증 코드가 발송되었습니다."}


# ─── 비밀번호 재설정 ────────────────────────────────────────────────
@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(data: PasswordResetRequest, db: Session = Depends(get_db)):
    """인증 코드 확인 후 비밀번호 변경"""
    redis = await get_redis()
    saved_code = await redis.get(f"reset_code:{data.email}")
    if not saved_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="인증 코드가 만료되었거나 존재하지 않습니다. 다시 발송해주세요.")
    if saved_code != data.code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="인증 코드가 일치하지 않습니다.")

    AuthService.reset_password_by_email(db, str(data.email), data.new_password)
    await redis.delete(f"reset_code:{data.email}")
    return {"message": "비밀번호가 변경되었습니다. 새 비밀번호로 로그인해주세요."}


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

    # 사용자 인증 성공 시 JWT 액세스 토큰 및 리프레시 토큰 생성 (user[0]: user_id)
    access_token = create_access_token(data={"sub": user[0]})
    refresh_token = create_refresh_token(data={"sub": user[0]})
    
    # 로그인 성공 시 토큰과 사용자 정보를 반환
    return {
        "message": "로그인 성공!",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user[0],
        "user_name": user[1]
    }


# @router.post("/refresh"): POST로 요청하면 리프레시 토큰으로 새 액세스 토큰 발급
@router.post("/refresh")
def refresh_access_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """리프레시 토큰으로 새 액세스 토큰 발급
    
    Args:
        request: 리프레시 토큰을 담은 요청
        
    Returns:
        dict: 새 액세스 토큰과 사용자 정보
        
    Raises:
        HTTPException: 리프레시 토큰이 유효하지 않거나 만료된 경우
    """
    try:
        # 1. 리프레시 토큰 디코딩 및 검증
        payload = jwt.decode(
            request.refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        # 2. 토큰 타입 확인 (refresh 토큰인지 검증)
        token_type = payload.get("type")
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 리프레시 토큰입니다."
            )
        
        # 3. 토큰에서 user_id 추출
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 토큰입니다."
            )
        
        # 4. 사용자 정보 확인 (DB에 존재하는 사용자인지 검증)
        user = AuthService.get_user_info(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="사용자를 찾을 수 없습니다."
            )
        
        # 5. 새 액세스 토큰 생성
        new_access_token = create_access_token(data={"sub": user_id})
        
        # 6. 새 액세스 토큰 반환
        return {
            "message": "토큰이 갱신되었습니다.",
            "access_token": new_access_token,
            "token_type": "bearer",
            "user_id": user_id,
            "user_name": user[1]
        }
        
    except JWTError as e:
        # 토큰 만료, 서명 불일치, 형식 오류 등
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="리프레시 토큰이 만료되었거나 유효하지 않습니다. 다시 로그인해주세요."
        )


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
