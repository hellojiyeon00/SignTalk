"""인증 서비스

회원가입, 로그인, 회원정보 관리 비즈니스 로직
PostgreSQL crypt 함수를 사용한 비밀번호 암호화
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

from app.api.schemas import UserSignup, UserLogin, UserUpdate


class AuthService:
    """인증 관련 비즈니스 로직 처리"""

    @staticmethod
    def create_user(db: Session, user_data: UserSignup):
        """회원가입 처리
        
        1. 아이디 중복 체크
        2. 비밀번호 암호화 (PostgreSQL crypt)
        3. DB 저장
        """
        # 아이디 중복 확인
        check_sql = text("""
            SELECT member_id FROM multicampus_schema.member 
            WHERE member_id = :id
        """)
        
        result = db.execute(check_sql, {"id": user_data.user_id}).fetchone()
        
        if result:
            raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")

        # 회원 정보 저장 (비밀번호는 DB에서 암호화)
        insert_sql = text("""
            INSERT INTO multicampus_schema.member (
                member_id, passwd, full_name, mobile_phone, 
                e_mail_address, deaf_muteness_section_code, create_user
            ) VALUES (
                :id, 
                crypt(:pw, gen_salt('bf')), 
                :name, :phone, :email, :is_deaf, :creator
            )
        """)

        params = {
            "id": user_data.user_id,
            "pw": user_data.password,
            "name": user_data.user_name,
            "phone": user_data.phone_number,
            "email": user_data.email,
            "is_deaf": user_data.is_deaf,
            "creator": user_data.user_id
        }

        try:
            db.execute(insert_sql, params)
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"가입 실패: {str(e)}")

    @staticmethod
    def authenticate_user(db: Session, login_data: UserLogin):
        """로그인 인증
        
        PostgreSQL crypt 함수로 비밀번호 검증
        
        Returns:
            tuple: (member_id, full_name) 또는 None
        """
        login_sql = text("""
            SELECT member_id, full_name 
            FROM multicampus_schema.member
            WHERE member_id = :id 
              AND passwd = crypt(:pw, passwd)
              AND delete_date IS NULL
        """)
        
        user = db.execute(login_sql, {
            "id": login_data.user_id, 
            "pw": login_data.password
        }).fetchone()
        
        return user

    @staticmethod
    def get_user_info(db: Session, user_id: str):
        """사용자 정보 조회
        
        Returns:
            tuple: (member_id, full_name, mobile_phone, e_mail_address)
        """
        sql = text("""
            SELECT member_id, full_name, mobile_phone, e_mail_address 
            FROM multicampus_schema.member 
            WHERE member_id = :id
        """)
        return db.execute(sql, {"id": user_id}).fetchone()

    @staticmethod
    def update_user(db: Session, update_data: UserUpdate):
        """회원정보 수정"""
        try:
            # 비밀번호 변경 포함 여부에 따라 SQL 분기
            if update_data.password:
                update_sql = text("""
                    UPDATE multicampus_schema.member
                    SET full_name = :name,
                        mobile_phone = :phone,
                        passwd = crypt(:pw, gen_salt('bf')),
                        update_date = CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
                        update_user = :id
                    WHERE member_id = :id
                """)
                params = {
                    "name": update_data.user_name, 
                    "phone": update_data.phone_number, 
                    "pw": update_data.password, 
                    "id": update_data.user_id
                }
            else:
                update_sql = text("""
                    UPDATE multicampus_schema.member
                    SET full_name = :name,
                        mobile_phone = :phone,
                        update_date = CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
                        update_user = :id
                    WHERE member_id = :id
                """)
                params = {
                    "name": update_data.user_name, 
                    "phone": update_data.phone_number, 
                    "id": update_data.user_id
                }

            db.execute(update_sql, params)
            db.commit()
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def delete_user(db: Session, user_id: str):
        """회원 탈퇴 (소프트 삭제)
        
        실제 데이터 삭제 대신 delete_date 기록
        """
        delete_sql = text("""
            UPDATE multicampus_schema.member
            SET delete_date = CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
                delete_user = :id
            WHERE member_id = :id
        """)
        
        try:
            db.execute(delete_sql, {"id": user_id})
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
