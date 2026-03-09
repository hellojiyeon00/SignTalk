"""재난문자 사용자별 발송 이력 모델 (characters_send.py)"""
from sqlalchemy import Column, Integer, TIMESTAMP, String, func
from app.core.database import Base

class CharactersSend(Base):
    __tablename__ = "characters_send"
    __table_args__ = {'schema': 'multicampus_schema'}

    # 복합 기본 키 (Primary Key가 2개입니다)
    character_id = Column(Integer, primary_key=True, nullable=False) # 발송된 문자 ID 
    member_no = Column(Integer, primary_key=True, nullable=False)    # 문자를 받은 회원 번호 
    
    send_date = Column(TIMESTAMP(timezone=False), nullable=False)    # 발송 일시 
    
    # 메타 정보
    create_user = Column(String(50), nullable=False) 
    create_date = Column(TIMESTAMP(timezone=False), nullable=False, server_default=func.now())
    update_user = Column(String(50), nullable=True) 
    update_date = Column(TIMESTAMP(timezone=False), nullable=True) 
    delete_user = Column(String(50), nullable=True)
    delete_date = Column(TIMESTAMP(timezone=False), nullable=True) 