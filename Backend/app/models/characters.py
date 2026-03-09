"""재난문자 수집 원본 모델 (characters.py)"""
from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from app.core.database import Base

class Characters(Base):
    __tablename__ = "characters"
    __table_args__ = {'schema': 'multicampus_schema'}

    character_id = Column(Integer, primary_key=True, autoincrement=True, nullable=False) # 문자 ID (IDENTITY 자동 생성) 
    character_type_code = Column(String(2), nullable=False) # EX(위급재난), EM(긴급재난), SA(안전안내) 등의 코드 
    character_content = Column(String, nullable=False)      # 실제 재난 문자 내용 
    
    # 공공데이터포털 제공 부가 정보
    disaster_sn = Column(Integer, nullable=True)                  # 일련번호 
    disaster_crt_dt = Column(TIMESTAMP(timezone=False), nullable=True) # 생성 일시 
    disaster_rcptn_rgn_nm = Column(String, nullable=True)         # 수신 지역명 
    disaster_emrg_step_nm = Column(String, nullable=True)         # 긴급 단계명 
    disaster_dst_se_nm = Column(String, nullable=True)            # 재해 구분명
    disaster_reg_ymd = Column(String(8), nullable=True)           # 등록 일자 (YYYYMMDD 형식) 
    disaster_mdfcn_ymd = Column(String(8), nullable=True)         # 수정 일자
    
    # 메타 정보
    create_user = Column(String(50), nullable=False)
    create_date = Column(TIMESTAMP(timezone=False), nullable=False, server_default=func.now()) 
    update_date = Column(TIMESTAMP(timezone=False), nullable=True) 
    delete_user = Column(String(50), nullable=True) 
    delete_date = Column(TIMESTAMP(timezone=False), nullable=True) 