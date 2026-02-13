"""데이터베이스 연결 및 세션 관리

SQLAlchemy를 사용한 PostgreSQL 연결 설정
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# 데이터베이스 엔진 생성
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True  # 연결 유효성 자동 검사
)

# 세션 팩토리 생성
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ORM 모델 베이스 클래스
Base = declarative_base()


def get_db():
    """데이터베이스 세션 의존성
    
    FastAPI 라우터에서 사용할 DB 세션을 생성하고 관리.
    요청 처리 후 자동으로 세션을 종료.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()