# backend/app/services/disaster_service.py

from sqlalchemy import text
from app.core.database import SessionLocal
import logging
import asyncio
import psycopg2
from datetime import datetime, timedelta, timezone

from app.core.config import settings

# 서버 로거 설정
logger = logging.getLogger("     disaster_service")

# 전역 재난문자 큐 (PostgreSQL NOTIFY 리스너가 채움)
disaster_queue = asyncio.Queue()


# 재난문자 관련 비즈니스 로직을 처리하는 클래스
class DisasterService:
    # @staticmethod: 정적 메서드로 정의하여 인스턴스 생성 없이 호출 가능
    @staticmethod
    def get_disaster_message(character_id: int):
        """
        트리거가 알려준 ID를 기반으로 재난문자의 상세 내용을 DB에서 가져옵니다.
        
        Returns:
            dict: {"id", "message", "type_code", "type_name"}
        """
        # DB 세션 생성
        db = SessionLocal()
        try:
            # SQL: 재난문자 상세 조회 (character_id로 조회, 등급 포함)
            sql = text("""
                SELECT character_id, character_content, character_type_code, disaster_emrg_step_nm
                FROM multicampus_schema.characters 
                WHERE character_id = :id
            """)
            
            # SQL 실행 및 결과 가져오기
            result = db.execute(sql, {"id": character_id}).fetchone()
            
            # result[0]=id, result[1]=message, result[2]=type_code, result[3]=emrg_step_nm
            if result:
                return {
                    "id": result[0], 
                    "message": result[1],
                    "type_code": result[2],  # EX(위급), EM(긴급), SA(안전안내)
                    "type_name": result[3] or result[2]  # 긴급단계명 (없으면 코드 사용)
                }
            return None
        
        # 예외 처리 및 세션 종료
        except Exception as e:
            logger.error(f"❌ [DB 에러] 재난 문자 조회 실패: {e}")
            return None
        finally:
            db.close()
    
    @staticmethod
    async def start_disaster_listener():
        """PostgreSQL NOTIFY 리스너 시작
        
        백그라운드에서 PostgreSQL의 NOTIFY를 감지하고 
        disaster_queue에 데이터를 추가합니다.
        """
        try:
            # DB 연결 (비동기 루프를 막지 않기 위해 자동 커밋 모드 사용)
            conn = psycopg2.connect(settings.DATABASE_URL)
            # 자동 커밋 모드 설정 (NOTIFY 수신을 위해 필요)
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            curs = conn.cursor()
            
            # DB에 NOTIFY 수신 대기 설정 (characters 테이블의 INSERT 이벤트를 감지)
            curs.execute('LISTEN "characters_INSERT";')
            logger.info("📡 재난 문자 PostgreSQL NOTIFY 수신 대기 시작...")

            while True:
                # 다른 비동기 작업들이 멈추지 않도록 1초씩 양보(sleep)하며 확인
                await asyncio.sleep(1)
                # DB에서 알림이 있는지 확인 (블로킹이 되지 않도록 poll 사용)
                conn.poll()
                
                # 만약 알림이 있다면:
                while conn.notifies:
                    # 알림 뭉치에서 하나를 꺼냄
                    notify = conn.notifies.pop(0)
                    # 알림 페이로드에서 character_id 추출(character_id는 트리거에서 보낸 값)
                    character_id = int(notify.payload)
                    
                    # 서비스 계층을 호출하여 메시지 내용 가져오기
                    alert_data = DisasterService.get_disaster_message(character_id)
                    
                    if alert_data:
                        # 한국 시간 설정
                        KST = timezone(timedelta(hours=9))
                        now_kst = datetime.now(KST).strftime("%H:%M")
                        
                        # 재난문자 데이터 준비 (등급 정보 포함)
                        disaster_data = {
                            "id": alert_data["id"],
                            "message": alert_data["message"],
                            "type_code": alert_data["type_code"],
                            "type_name": alert_data["type_name"],
                            "time": now_kst
                        }
                        
                        # 큐에 추가 (모든 SSE 연결이 이 큐에서 읽음)
                        await disaster_queue.put(disaster_data)
                        logger.info(f"🚨 [재난문자 {alert_data['type_code']}] 큐에 추가: {alert_data['message'][:20]}...")

        except Exception as e:
            logger.error(f"❌ 재난 문자 PostgreSQL 리스너 에러: {e}")
    
    @staticmethod
    async def generate_disaster_stream(user_id: str, request):
        """SSE 이벤트 생성기
        
        Args:
            user_id: 사용자 ID (나중에 위치 필터링에 사용)
            request: FastAPI Request 객체 (연결 확인용)
            
        Yields:
            dict: SSE 이벤트 데이터
        """
        logger.info(f"📡 [SSE] 사용자 {user_id} 재난문자 스트림 연결")
        
        try:
            while True:
                # 클라이언트 연결 확인
                if await request.is_disconnected():
                    logger.info(f"🔌 [SSE] 사용자 {user_id} 연결 종료")
                    break
                
                # 재난문자 큐에서 데이터 가져오기 (타임아웃 1초)
                try:
                    disaster_data = await asyncio.wait_for(
                        disaster_queue.get(), 
                        timeout=1.0
                    )
                    
                    # TODO: 사용자 위치 기반 필터링 (나중에 구현)
                    # user_location = get_user_location(user_id)
                    # if not is_location_match(disaster_data["region"], user_location):
                    #     continue
                    
                    # SSE 이벤트 전송
                    yield {
                        "event": "disaster",
                        "id": str(disaster_data.get("id", "")),
                        "data": disaster_data
                    }
                    
                    logger.info(f"🚨 [SSE] 재난문자 전송 → {user_id}: {disaster_data['message'][:20]}...")
                    
                except asyncio.TimeoutError:
                    # 타임아웃 시 연결 유지를 위한 ping 이벤트
                    yield {
                        "event": "ping",
                        "data": "keep-alive"
                    }
                    
        except asyncio.CancelledError:
            logger.info(f"❌ [SSE] 사용자 {user_id} 스트림 취소됨")
        except Exception as e:
            logger.error(f"❌ [SSE] 스트림 오류: {e}")
