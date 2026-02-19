"""채팅 서비스

채팅방 관리 및 메시지 관련 비즈니스 로직
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException


class ChatService:
    """채팅 관련 비즈니스 로직 처리"""

    @staticmethod
    def search_users(db: Session, my_id: str, name: str = None, member_id: str = None):
        """사용자 검색
        
        이름 또는 아이디로 검색 (본인 제외)
        
        Returns:
            list: [{"member_no", "member_id", "user_name"}, ...]
        """
        if not name and not member_id:
            return []
        
        query_str = """
            SELECT member_no, member_id, full_name 
            FROM multicampus_schema.member
            WHERE member_id != :my_id
        """
        params = {"my_id": my_id}
        
        if name:
            query_str += " AND full_name LIKE :name"
            params["name"] = f"%{name}%"
        
        if member_id:
            query_str += " AND member_id LIKE :member_id"
            params["member_id"] = f"%{member_id}%"
            
        results = db.execute(text(query_str), params).fetchall()
        
        return [
            {"member_no": row[0], "member_id": row[1], "user_name": row[2]} 
            for row in results
        ]

    @staticmethod
    def create_or_get_room(db: Session, my_id: str, target_id: str):
        """채팅방 생성 또는 조회
        
        두 사용자 간 1:1 채팅방 조회/생성
        
        Returns:
            dict: {"room_id": int, "message": str}
        """
        # 회원 번호 조회
        get_no_sql = text("SELECT member_no FROM multicampus_schema.member WHERE member_id = :id")
        my_no = db.execute(get_no_sql, {"id": my_id}).scalar()
        target_no = db.execute(get_no_sql, {"id": target_id}).scalar()
        
        if not my_no or not target_no:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # 기존 방 확인
        check_room_sql = text("""
            SELECT talk_room_id FROM multicampus_schema.talk_room
            WHERE (member_no1 = :m1 AND member_no2 = :m2)
               OR (member_no1 = :m2 AND member_no2 = :m1)
        """)
        room_id = db.execute(check_room_sql, {"m1": my_no, "m2": target_no}).scalar()

        if room_id:
            return {"room_id": room_id, "message": "이미 존재하는 채팅방입니다."}

        # 새 방 생성
        create_room_sql = text("""
            INSERT INTO multicampus_schema.talk_room (
                talk_room_id, member_no1, member_no2, create_user
            ) VALUES (
                nextval('multicampus_schema.talk_room_id_s'), :m1, :m2, :creator
            ) RETURNING talk_room_id
        """)
        
        try:
            new_room_id = db.execute(create_room_sql, {
                "m1": my_no, "m2": target_no, "creator": my_id
            }).scalar()
            
            db.commit()
            return {"room_id": new_room_id, "message": "새 채팅방 생성 완료"}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="채팅방 생성 실패")

    @staticmethod
    def get_my_rooms(db: Session, user_id: str):
        """내 채팅방 목록 조회
        
        삭제되지 않은 친구만 표시 (delete_date IS NULL)
        
        Returns:
            list: [{"user_id", "user_name"}, ...]
        """
        # 내 회원 번호 조회
        my_no_sql = text("SELECT member_no FROM multicampus_schema.member WHERE member_id = :id")
        my_no = db.execute(my_no_sql, {"id": user_id}).scalar()

        # 채팅 목록 조회 (삭제되지 않은 것만, UNION으로 member_no1, member_no2 양쪽 처리)
        chat_list_sql = text("""
            SELECT A1.member_no1 AS member_no,
                   (SELECT CC1.member_id FROM multicampus_schema.member CC1 WHERE A1.member_no1 = CC1.member_no) AS member_id,
                   (SELECT CC1.full_name FROM multicampus_schema.member CC1 WHERE A1.member_no1 = CC1.member_no) AS full_name
            FROM (
                SELECT BB1.member_no1, BB1.member_no2
                FROM multicampus_schema.member AA1, multicampus_schema.talk_room BB1
                WHERE AA1.member_no = :my_no 
                  AND (AA1.member_no = BB1.member_no1 OR AA1.member_no = BB1.member_no2)
                  AND BB1.delete_date IS NULL
            ) A1
            WHERE A1.member_no1 != :my_no
            UNION
            SELECT A2.member_no2 AS member_no,
                   (SELECT CC2.member_id FROM multicampus_schema.member CC2 WHERE A2.member_no2 = CC2.member_no) AS member_id,
                   (SELECT CC2.full_name FROM multicampus_schema.member CC2 WHERE A2.member_no2 = CC2.member_no) AS full_name
            FROM (
                SELECT BB2.member_no1, BB2.member_no2
                FROM multicampus_schema.member AA2, multicampus_schema.talk_room BB2
                WHERE AA2.member_no = :my_no 
                  AND (AA2.member_no = BB2.member_no1 OR AA2.member_no = BB2.member_no2)
                  AND BB2.delete_date IS NULL
            ) A2
            WHERE A2.member_no2 != :my_no
        """)
        
        results = db.execute(chat_list_sql, {"my_no": my_no}).fetchall()
        
        return [
            {"user_id": row[1], "user_name": row[2]} 
            for row in results
        ]

    @staticmethod
    def get_chat_history(db: Session, room_id: int):
        """채팅방 대화 내역 조회
        
        Returns:
            list: [{"message", "sender", "sender_name", "date"}, ...]
        """
        history_sql = text("""
            SELECT T.message, M.member_id, M.full_name, T.talk_date
            FROM multicampus_schema.talk T
            JOIN multicampus_schema.member M ON T.member_no = M.member_no
            WHERE T.talk_room_id = :r_id
            ORDER BY T.talk_date ASC
        """)
        
        results = db.execute(history_sql, {"r_id": room_id}).fetchall()
        
        return [
            {
                "message": row[0], 
                "sender": row[1],
                "sender_name": row[2],
                "date": row[3].strftime("%H:%M")
            } for row in results
        ]

    @staticmethod
    def delete_friend(db: Session, my_id: str, friend_id: str):
        """친구 삭제 (소프트 삭제)
        
        delete_user와 delete_date 컬럼을 업데이트하여 소프트 삭제 처리
        
        Returns:
            dict: {"message": str}
        """
        # 회원 번호 조회
        get_no_sql = text("SELECT member_no FROM multicampus_schema.member WHERE member_id = :id")
        my_no = db.execute(get_no_sql, {"id": my_id}).scalar()
        friend_no = db.execute(get_no_sql, {"id": friend_id}).scalar()
        
        if not my_no or not friend_no:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        # 채팅방 소프트 삭제 (delete_user, delete_date 업데이트)
        delete_sql = text("""
            UPDATE multicampus_schema.talk_room
            SET delete_date = CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
                delete_user = :deleter
            WHERE ((member_no1 = :m1 AND member_no2 = :m2) 
                OR (member_no1 = :m2 AND member_no2 = :m1))
              AND delete_date IS NULL
        """)
        
        try:
            result = db.execute(delete_sql, {
                "m1": my_no, "m2": friend_no, "deleter": my_id
            })
            db.commit()
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="차단할 친구를 찾을 수 없습니다.")
            
            return {"message": "친구가 차단되었습니다."}
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"친구 차단 실패: {str(e)}")

    @staticmethod
    def get_friend_list(db: Session, user_id: str):
        """친구 목록 조회 (설정 창용)
        
        모든 친구 표시 (차단된 친구 포함)
        
        Returns:
            list: [{"user_id", "user_name", "is_blocked"}, ...]
        """
        # 내 회원 번호 조회
        my_no_sql = text("SELECT member_no FROM multicampus_schema.member WHERE member_id = :id")
        my_no = db.execute(my_no_sql, {"id": user_id}).scalar()

        # 채팅 목록 조회 (모든 친구, 차단 여부 포함)
        friend_list_sql = text("""
            SELECT DISTINCT 
                M.member_id AS friend_id,
                M.full_name AS friend_name,
                CASE WHEN TR.delete_date IS NOT NULL THEN true ELSE false END AS is_blocked
            FROM multicampus_schema.talk_room TR
            JOIN multicampus_schema.member M ON (
                (TR.member_no1 = :my_no AND TR.member_no2 = M.member_no) OR
                (TR.member_no2 = :my_no AND TR.member_no1 = M.member_no)
            )
            WHERE (TR.member_no1 = :my_no OR TR.member_no2 = :my_no)
              AND M.member_no != :my_no
            ORDER BY is_blocked, M.full_name
        """)
        
        results = db.execute(friend_list_sql, {"my_no": my_no}).fetchall()
        
        return [
            {
                "user_id": row[0],
                "user_name": row[1],
                "is_blocked": row[2]
            } for row in results
        ]

    @staticmethod
    def unblock_friend(db: Session, my_id: str, friend_id: str):
        """친구 차단 해제
        
        delete_user와 delete_date를 NULL로 설정하여 차단 해제
        
        Returns:
            dict: {"message": str}
        """
        # 회원 번호 조회
        get_no_sql = text("SELECT member_no FROM multicampus_schema.member WHERE member_id = :id")
        my_no = db.execute(get_no_sql, {"id": my_id}).scalar()
        friend_no = db.execute(get_no_sql, {"id": friend_id}).scalar()
        
        if not my_no or not friend_no:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        # 차단 해제 (delete_date, delete_user를 NULL로)
        unblock_sql = text("""
            UPDATE multicampus_schema.talk_room
            SET delete_date = NULL,
                delete_user = NULL,
                update_date = CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
                update_user = :updater
            WHERE ((member_no1 = :m1 AND member_no2 = :m2) 
                OR (member_no1 = :m2 AND member_no2 = :m1))
              AND delete_date IS NOT NULL
        """)
        
        try:
            result = db.execute(unblock_sql, {
                "m1": my_no, "m2": friend_no, "updater": my_id
            })
            db.commit()
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="차단 해제할 친구를 찾을 수 없습니다.")
            
            return {"message": "차단이 해제되었습니다."}
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"차단 해제 실패: {str(e)}")

