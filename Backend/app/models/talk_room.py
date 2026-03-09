"""채팅방 모델

TalkRoom 테이블 ORM 모델 정의
"""
from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from app.core.database import Base


class TalkRoom(Base):
    """1:1 채팅방 정보 테이블"""
    
    __tablename__ = "talk_room"
    __table_args__ = {'schema': 'multicampus_schema'}

    # 기본 키
    talk_room_id = Column(Integer, primary_key=True, index=True, nullable=False)
    
    # 참여자
    member_no1 = Column(Integer, nullable=False)
    member_no2 = Column(Integer, nullable=False)
    
    # 메타 정보 (생성/수정/삭제 이력)
    create_user = Column(String(50), nullable=False)
    create_date = Column(TIMESTAMP(timezone=False), nullable=False, server_default=func.now())
    update_user = Column(String(50), nullable=True)
    update_date = Column(TIMESTAMP(timezone=False), nullable=True)
    delete_user = Column(String(50), nullable=True)
    delete_date = Column(TIMESTAMP(timezone=False), nullable=True)

    def __repr__(self):
        return f"<TalkRoom(id={self.talk_room_id}, members={self.member_no1}&{self.member_no2})>"
