"""대화 상세 및 수어 매핑 모델 (talk_detail.py)"""
from sqlalchemy import Column, Integer, SmallInteger, String, Text, TIMESTAMP, func
from app.core.database import Base

class TalkDetail(Base):
    __tablename__ = "talk_detail"
    __table_args__ = {'schema': 'multicampus_schema'}

    # 복합 기본 키 (Primary Key가 4개입니다)
    talk_room_id = Column(Integer, primary_key=True, nullable=False) # 대화방 ID 
    member_no = Column(Integer, primary_key=True, nullable=False)    # 보낸 회원 번호 
    talk_date = Column(TIMESTAMP(timezone=False), primary_key=True, nullable=False) # 대화 일시 (정의서의 tail_date 오타 보정) 
    word_order_no = Column(SmallInteger, primary_key=True, nullable=False) # 단어별 순서 번호 (예: 1, 2, 3...)
    
    # 단어 및 수어 영상 정보
    word_name = Column(String, nullable=False) # 대화 시점의 단어명 
    url_path = Column(String, nullable=False)  # 대화 시점의 수어 영상 URL 혹은 경로 
    vector = Column(Text, nullable=False)      # AI 분석용 대화 시점의 Vector 값 
    
    # 메타 정보
    create_user = Column(String(50), nullable=False) 
    create_date = Column(TIMESTAMP(timezone=False), nullable=False, server_default=func.now())
    update_user = Column(String(50), nullable=True) 
    update_date = Column(TIMESTAMP(timezone=False), nullable=True) 
    delete_user = Column(String(50), nullable=True) # (물리적 삭제 DELETE FROM 시 사용)
    delete_date = Column(TIMESTAMP(timezone=False), nullable=True) 