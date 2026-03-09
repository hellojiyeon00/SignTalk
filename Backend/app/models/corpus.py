"""수어 말뭉치 사전 모델 (corpus.py)"""
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, func
from app.core.database import Base

class Corpus(Base):
    __tablename__ = "corpus"
    __table_args__ = {'schema': 'multicampus_schema'}

    word_id = Column(Integer, primary_key=True, nullable=False) # 단어 고유 ID 
    word_name = Column(String, nullable=False) # 단어명 
    url_path = Column(String, nullable=False)  # 수어 영상 URL 또는 업로드된 mp4 경로/파일명 
    vector = Column(Text, nullable=False)      # 단어의 특징점 Vector 데이터 
    
    # 메타 정보
    create_user = Column(String(50), nullable=False) 
    create_date = Column(TIMESTAMP(timezone=False), nullable=False, server_default=func.now()) 
    update_user = Column(String(50), nullable=True)
    update_date = Column(TIMESTAMP(timezone=False), nullable=True)
    delete_user = Column(String(50), nullable=True) 
    delete_date = Column(TIMESTAMP(timezone=False), nullable=True) 