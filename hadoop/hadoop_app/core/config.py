"""애플리케이션 설정 관리

.env 파일로부터 환경 변수를 로드하고 검증
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """애플리케이션 설정 클래스"""

    # HDFS 설정
    HDFS_USER: str
    HDFS_PASSWORD: str
    HDFS_HOST: str
    HDFS_PORT: str

    @property
    def HDFS_URL(self) -> str:
        """HDFS 연결 URL 생성"""
        return f"http://{self.HDFS_HOST}:{self.HDFS_PORT}"


    # .env 파일 경로 계산 (hadoop/app/core -> project root)
    _current_file = os.path.abspath(__file__)
    _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_current_file))))
    _env_file_path = os.path.join(_project_root, ".env")

    model_config = SettingsConfigDict(
        env_file=_env_file_path,
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()