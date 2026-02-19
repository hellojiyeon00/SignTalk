# backend/app/services/disaster_service.py

from sqlalchemy import text
from app.core.database import SessionLocal
import logging

logger = logging.getLogger("disaster_service")

class DisasterService:
    @staticmethod
    def get_disaster_message(character_id: int):
        """
        트리거가 알려준 ID를 기반으로 재난문자의 상세 내용을 DB에서 가져옵니다.
        """
        db = SessionLocal()
        try:
            sql = text("""
                SELECT character_id, message 
                FROM multicampus_schema.characters 
                WHERE character_id = :id
            """)
            result = db.execute(sql, {"id": character_id}).fetchone()
            
            if result:
                return {"id": result[0], "message": result[1]}
            return None
            
        except Exception as e:
            logger.error(f"❌ [DB 에러] 재난 문자 조회 실패: {e}")
            return None
        finally:
            db.close()