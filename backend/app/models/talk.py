"""채팅 메시지 모델 (talk.py)"""
from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from app.core.database import Base

class Talk(Base):
    __tablename__ = "talk"
    __table_args__ = {'schema': 'multicampus_schema'}

    # 복합 기본 키 (Primary Key가 3개입니다)
    talk_room_id = Column(Integer, primary_key=True, nullable=False) # 어떤 방에서 보냈는지 
    member_no = Column(Integer, primary_key=True, nullable=False)    # 누가 보냈는지 
    talk_date = Column(TIMESTAMP(timezone=False), primary_key=True, nullable=False) # 언제 보냈는지 
    
    # 대화 내용
    message = Column(String, nullable=False) # 실제 채팅 텍스트 내용
    
    # 읽은 메시지 여부 (confirm_yn bpchar(1) DEFAULT 'N'::bpchar NOT NULL)
    confirm_yn = Column(String(1), nullable=False, server_default='N')
    
    # 메타 정보 (생성/수정/삭제 이력)
    create_user = Column(String(50), nullable=False) # 데이터를 처음 넣은 사람 
    create_date = Column(TIMESTAMP(timezone=False), nullable=False, server_default=func.now()) # 데이터 생성 시간 
    update_user = Column(String(50), nullable=True)  # 데이터를 수정한 사람 
    update_date = Column(TIMESTAMP(timezone=False), nullable=True) # 데이터 수정 시간
    delete_user = Column(String(50), nullable=True)  # 논리적 삭제 처리를 한 사람
    delete_date = Column(TIMESTAMP(timezone=False), nullable=True) # 논리적 삭제가 발생한 시간