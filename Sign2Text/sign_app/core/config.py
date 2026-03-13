"""애플리케이션 설정 관리

.env 파일로부터 환경 변수를 로드하고 검증
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """애플리케이션 설정 클래스"""

    # ===== 모델 경로 =====
    # LSTM
    LSTM_MODEL_PATH: str
    # GLOSS_LABEL
    GLOSS_LABEL_PATH: str
    # LLM API
    LLM_URL: str
    LLM_MODEL: str
    LLM_API_KEY: str

    # .env 파일 경로 계산 (Sign2Text/model_app/core -> project root)
    _current_file = os.path.abspath(__file__)
    _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_current_file))))
    _env_file_path = os.path.join(_project_root, ".env")

    model_config = SettingsConfigDict(
        env_file=_env_file_path,
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()