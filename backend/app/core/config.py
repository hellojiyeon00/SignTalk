"""애플리케이션 설정 관리

.env 파일로부터 환경 변수를 로드하고 검증
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """애플리케이션 설정 클래스"""
    
    # 데이터베이스 설정
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: str
    DB_NAME: str
    
    # Redis 설정
    REDIS_PASSWORD: str
    REDIS_HOST: str
    REDIS_PORT: str

    # JWT 설정
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    
    # Kakao API 설정
    KAKAO_REST_API_KEY: str = "YOUR_KAKAO_REST_API_KEY_HERE"

    @property
    def DATABASE_URL(self) -> str:
        """SQLAlchemy 데이터베이스 연결 URL 생성"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def REDIS_URL(self) -> str:
        """Redis 연결 URL 생성"""
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}"

    # .env 파일 경로 계산 (backend/app/core -> backend)
    _current_file = os.path.abspath(__file__)
    _backend_root = os.path.dirname(os.path.dirname(os.path.dirname(_current_file)))
    _env_file_path = os.path.join(_backend_root, ".env")

    model_config = SettingsConfigDict(
        env_file=_env_file_path,
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()