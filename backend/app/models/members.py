"""회원 모델

Member 테이블 ORM 모델 정의
"""
from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, func
from app.core.database import Base


class Member(Base):
    """회원 정보 테이블"""
    
    __tablename__ = "member"
    __table_args__ = {'schema': 'multicampus_schema'}

    # 기본 키
    member_no = Column(Integer, primary_key=True, index=True)
    
    # 회원 정보
    member_id = Column(String(50), unique=True, index=True, nullable=False)
    passwd = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    mobile_phone = Column(String(50), nullable=False)
    e_mail_address = Column(String, nullable=False)
    deaf_muteness_section_code = Column(Boolean, nullable=False, default=True)
    
    # 메타 정보 (생성/수정/삭제 이력)
    create_user = Column(String(50), nullable=False)
    create_date = Column(TIMESTAMP(timezone=False), nullable=False, server_default=func.now())
    update_user = Column(String(50), nullable=True)
    update_date = Column(TIMESTAMP(timezone=False), nullable=True)
    delete_user = Column(String(50), nullable=True)
    delete_date = Column(TIMESTAMP(timezone=False), nullable=True)

    def __repr__(self):
        return f"<Member(no={self.member_no}, id='{self.member_id}', name='{self.full_name}')>"
