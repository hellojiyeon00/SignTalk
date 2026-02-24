"""애플리케이션 설정 관리

.env 파일로부터 환경 변수를 로드하고 검증
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """애플리케이션 설정 클래스"""

    # Redis 설정
    REDIS_PASSWORD: str
    REDIS_HOST: str
    REDIS_PORT: str

    # ===== 모델 경로 =====
    # LSTM
    LSTM_MODEL_PATH: str
    # GLOSS_LABEL
    GLOSS_LABEL_PATH: str
    # LLM API
    LLM_URL: str
    LLM_MODEL: str
    LLM_API_KEY: str

    @property
    def REDIS_URL(self) -> str:
        """Redis 연결 URL 생성"""
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}"

    # .env 파일 경로 계산 (backend/app/core -> project root)
    _current_file = os.path.abspath(__file__)
    _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_current_file))))
    _env_file_path = os.path.join(_project_root, ".env")

    model_config = SettingsConfigDict(
        env_file=_env_file_path,
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()