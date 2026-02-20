"""인증 서비스

회원가입, 로그인, 회원정보 관리 비즈니스 로직
PostgreSQL crypt 함수를 사용한 비밀번호 암호화
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

from app.api.schemas import UserSignup, UserLogin, UserUpdate


# 인증 클래스 AuthService 정의
class AuthService:
    """인증 관련 비즈니스 로직 처리"""

    @staticmethod
    def create_user(db: Session, user_data: UserSignup):
        """회원가입 처리
        
        1. 아이디 중복 체크
        2. 비밀번호 암호화 (PostgreSQL crypt)
        3. DB 저장
        """
        
        # 아이디 중복 확인 (:id는 빈칸으로 두고 params로 전달)
        check_sql = text("""
            SELECT member_id FROM multicampus_schema.member 
            WHERE member_id = :id
        """)
        
        # db.execute()로 SQL 실행 후 fetchone()으로 결과 가져오기
        result = db.execute(check_sql, {"id": user_data.user_id}).fetchone()
        
        # 이미 존재하는 아이디가 있으면 400 Bad Request 예외 발생
        if result:
            raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")

        # 새 회원 정보 저장 (비밀번호는 DB에서 암호화)
        # crpyt(:pw, gen_salt('bf')): bcrypt 알고리즘으로 비밀번호 해싱
        # gen_salt('bf')는 bcrypt용 솔트 생성 함수 (솔트는 매번 다르게 생성되어 보안 강화)
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

        # 빈칸(:id, :pw 등)에 실제 값 전달
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
            # DB에 회원 정보 저장
            db.execute(insert_sql, params)
            
            # 저장 완료 후 커밋
            db.commit()
        except Exception as e:
            # 저장 실패 시 롤백하여 DB 상태 원복 (DB 꼬임 방지)
            db.rollback()
            raise HTTPException(status_code=500, detail=f"가입 실패: {str(e)}")


    @staticmethod
    def authenticate_user(db: Session, login_data: UserLogin):
        """로그인 인증
        
        PostgreSQL crypt 함수로 비밀번호 검증
        
        Returns:
            tuple: (member_id, full_name) 또는 None
        """
        
        # 로그인 SQL 실행(DB에 저장된 암호화된 비밀번호와 입력된 비밀번호를 crypt 함수로 비교)
        login_sql = text("""
            SELECT member_id, full_name 
            FROM multicampus_schema.member
            WHERE member_id = :id 
              AND passwd = crypt(:pw, passwd)
              AND delete_date IS NULL
        """)
        
        # db.execute()로 SQL 실행 후 fetchone()으로 결과 가져오기
        user = db.execute(login_sql, {
            "id": login_data.user_id, 
            "pw": login_data.password
        }).fetchone()
        
        # 인증 실패 시 None 반환, 성공 시 사용자 정보 튜플 반환
        return user

    @staticmethod
    def get_user_info(db: Session, user_id: str):
        """사용자 정보 조회
        
        Returns:
            tuple: (member_id, full_name, mobile_phone, e_mail_address)
        """
        
        # 사용자 정보 조회 SQL 실행 (회원 탈퇴하지 않은 사용자만 조회)
        sql = text("""
            SELECT member_id, full_name, mobile_phone, e_mail_address 
            FROM multicampus_schema.member 
            WHERE member_id = :id
                AND delete_date IS NULL
        """)
        
        # db.execute()로 SQL 실행 후 fetchone()으로 결과 가져오기
        return db.execute(sql, {"id": user_id}).fetchone()

    @staticmethod
    def update_user(db: Session, update_data: UserUpdate):
        """회원정보 수정"""
        
        # 회원정보를 업데이트하는 SQL 작성
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
                
                # 빈칸(:name, :phone, :pw 등)에 실제 값 전달
                params = {
                    "name": update_data.user_name, 
                    "phone": update_data.phone_number, 
                    "pw": update_data.password, 
                    "id": update_data.user_id
                }
            
            # 비밀번호 변경이 없으면 패스워드 업데이트 부분 제외
            else:
                update_sql = text("""
                    UPDATE multicampus_schema.member
                    SET full_name = :name,
                        mobile_phone = :phone,
                        update_date = CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
                        update_user = :id
                    WHERE member_id = :id
                """)
                
                # 빈칸(:name, :phone 등)에 실제 값 전달
                params = {
                    "name": update_data.user_name, 
                    "phone": update_data.phone_number, 
                    "id": update_data.user_id
                }

            # DB에 회원 정보 업데이트
            db.execute(update_sql, params)
            
            # 업데이트 완료 후 커밋
            db.commit()
        except Exception as e:
            # 업데이트 실패 시 롤백하여 DB 상태 원복 (DB 꼬임 방지)
            db.rollback()
            raise e

    @staticmethod
    def delete_user(db: Session, user_id: str):
        """회원 탈퇴 (소프트 삭제)
        
        실제 데이터 삭제 대신 delete_date 기록
        """
        
        # 회원 탈퇴를 처리하는 SQL 작성 (delete_date와 delete_user 업데이트)
        delete_sql = text("""
            UPDATE multicampus_schema.member
            SET delete_date = CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
                delete_user = :id
            WHERE member_id = :id
        """)
        
        try:
            # DB에 회원 탈퇴 처리 (소프트 삭제)
            db.execute(delete_sql, {"id": user_id})
            # 탈퇴 처리 완료 후 커밋
            db.commit()
        except Exception as e:
            # 탈퇴 처리 실패 시 롤백하여 DB 상태 원복 (DB 꼬임 방지)
            db.rollback()
            raise e
