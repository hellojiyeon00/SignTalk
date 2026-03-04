# backend/app/services/disaster_service.py

import logging
import asyncio
import json
from datetime import datetime, timedelta, timezone
from aiokafka import AIOKafkaConsumer # 비동기 Kafka 컨슈머 라이브러리 임포트

from app.core.config import settings

# 서버 터미널에 로그를 예쁘게 찍기 위한 설정입니다.
logger = logging.getLogger("disaster_service")

# aiokafka의 상세 로그 숨기기 (에러만 표시)
logging.getLogger("aiokafka").setLevel(logging.WARNING)

KAFKA_TOPIC = 'Topic_characters'

# 연결된 모든 클라이언트의 큐 목록 (브로드캐스트용)
# connected_clients = []
connected_clients = {}

# Kafka consumer 전역 변수 (종료 시 정리를 위해)
kafka_consumer = None
kafka_listener_task = None

class DisasterService:
    
    @staticmethod
    async def start_disaster_listener():
        """
        [Kafka 리스너 함수]
        FastAPI 서버가 켜질 때 백그라운드에서 무한히 실행되며, 
        Kafka 우체통(Topic)에 새 재난문자가 오는지 24시간 감시합니다.
        """
        global kafka_consumer
        
        # Kafka가 비활성화되어 있으면 리스너를 시작하지 않음
        if not settings.KAFKA_ENABLED:
            logger.warning("⚠️ Kafka가 비활성화되어 있습니다. (.env에서 KAFKA_ENABLED=true로 설정하세요)")
            logger.info("💡 재난문자를 받으려면 Kafka 서버 설정을 확인하고 KAFKA_ENABLED=true로 변경하세요.")
            return
        
        retry_count = 0
        max_retries = 3  # 최대 재시도 횟수
        
        while True:  # 연결 실패 시 재시도를 위한 외부 루프
            try:
                # 1. Kafka 우체국에서 데이터를 꺼내올 '구독자(Consumer)' 객체를 만듭니다.
                kafka_consumer = AIOKafkaConsumer(
                    KAFKA_TOPIC,                     # 창주님이 만든 Kafka 우체통(토픽) 이름입니다.
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,     # Kafka 서버의 주소와 포트입니다.
                    group_id='disaster_consumer_group',     # 컨슈머 그룹 ID (필수) - 같은 그룹은 메시지를 나눠서 받습니다.
                    # 받은 데이터는 010101 같은 바이트(Byte) 형태이므로, 이를 파이썬 딕셔너리(JSON)로 자동 번역해 주는 기능입니다.
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')), 
                    auto_offset_reset='earliest',           # 서버가 꺼진 동안 밀린 메시지를 마지막으로 읽은 지점부터 이어서 받습니다.
                    enable_auto_commit=True,                # 메시지를 읽었다는 처리(오프셋 커밋)를 자동으로 합니다.
                    request_timeout_ms=30000,               # 요청 타임아웃 30초
                    connections_max_idle_ms=540000          # 연결 유지 시간 9분
                )
                
                # 2. Kafka 서버와 연결을 시작합니다 (타임아웃 10초)
                await asyncio.wait_for(kafka_consumer.start(), timeout=10.0)
                logger.info(f"✅ Kafka 연결됨")
                retry_count = 0  # 연결 성공 시 재시도 카운터 초기화

                # 3. 무한 루프를 돌며 우체통에 편지가 들어올 때까지 문 앞에서 대기합니다.
                async for msg in kafka_consumer:
                    try:
                        # 편지가 도착하면 껍데기를 까서 안의 딕셔너리 데이터만 빼냅니다.
                        data = msg.value 
                        
                        # 4. 한국 시간(KST)으로 현재 시간을 구합니다.
                        KST = timezone(timedelta(hours=9))
                        now_kst = datetime.now(KST).strftime("%H:%M")
                        
                        # 5. 프론트엔드(chat.js)가 화면에 띄우기 좋게 데이터를 예쁘게 포장합니다.
                        disaster_data = {
                            "id": str(int(datetime.now().timestamp())),           # 화면에서 쓸 임시 고유 ID를 부여합니다.
                            "message": data.get("character_content", "내용 없음"), # 재난문자 실제 내용
                            "type_code": data.get("character_type_code", "EM"),   # EX(위급), EM(긴급), SA(안전)
                            "type_name": data.get("disaster_emrg_step_nm", "긴급재난"), # 재난 이름 (예: 홍수, 지진)
                            "disaster_type": data.get("disaster_dst_se_nm", "기타"), # 재난 유형 (예: 지진, 홍수, 태풍)
                            "region": data.get("disaster_rcptn_rgn_nm", ""),      # 발생 지역 (예: 서울특별시 강남구)
                            "time": now_kst                                       # 받은 시간
                        }
                        
                        # 6. 포장된 데이터를 모든 연결된 클라이언트에게 브로드캐스트합니다.
                        if connected_clients:
                            # 모든 클라이언트의 큐에 동일한 메시지 전송
                            for client_queue in list(connected_clients.values()):
                                try:
                                    await client_queue.put(disaster_data)
                                except Exception as e:
                                    logger.error(f"❌ [Kafka] 클라이언트 큐 전송 오류: {e}")
                            
                            logger.info(f"🚨 [Kafka] {disaster_data['type_code']} [{disaster_data['region']}] {disaster_data['message'][:30]}... → {len(connected_clients)}명")
                        
                    except json.JSONDecodeError as je:
                        logger.error(f"❌ [Kafka] JSON 파싱 오류: {je}")
                    except Exception as e:
                        logger.error(f"❌ [Kafka] 메시지 처리 중 오류: {e}")
                        
            except asyncio.TimeoutError:
                retry_count += 1
                logger.error(f"❌ Kafka 연결 시간 초과 (시도 {retry_count}/{max_retries})")
                
                if retry_count >= max_retries:
                    logger.warning("⚠️ Kafka 연결 실패. 더 이상 재시도하지 않습니다.")
                    logger.warning("💡 해결 방법:")
                    logger.warning("   1. Kafka 서버 실행 여부: sudo systemctl status kafka")
                    logger.warning("   2. 포트 확인: nc -zv 56.155.47.51 8908")
                    logger.warning("   3. 방화벽 설정: sudo ufw allow 8908")
                    logger.warning("   4. Kafka server.properties:")
                    logger.warning("      listeners=PLAINTEXT://0.0.0.0:8908")
                    logger.warning("      advertised.listeners=PLAINTEXT://56.155.47.51:8908")
                    logger.warning("   5. 임시 비활성화: .env에서 KAFKA_ENABLED=false")
                    break  # 재시도 중단
                    
                await asyncio.sleep(5)  # 5초 대기 후 재시도
                
            except Exception as e:
                # Kafka 연결 실패 또는 치명적 에러
                retry_count += 1
                logger.error(f"❌ Kafka 리스너 오류 발생: {type(e).__name__}: {e}")
                
                if retry_count >= max_retries:
                    logger.warning("⚠️ Kafka 연결 실패. 재난문자 기능이 비활성화됩니다.")
                    break  # 재시도 중단
                    
                logger.info(f"🔄 {5 * retry_count}초 후 Kafka 재연결 시도... ({retry_count}/{max_retries})")
                await asyncio.sleep(5 * retry_count)  # 점진적 대기
                
            finally:
                # 7. 연결이 있었다면 안전하게 종료
                if kafka_consumer is not None:
                    try:
                        logger.info("🔄 Kafka consumer 종료 중...")
                        await kafka_consumer.stop()
                        logger.info("✅ Kafka consumer 정상 종료됨")
                    except Exception as e:
                        logger.error(f"❌ Kafka 종료 중 오류: {e}")
                kafka_consumer = None
    
    @staticmethod
    async def stop_disaster_listener():
        """
        [Kafka 리스너 종료]
        서버 종료 시 Kafka consumer를 안전하게 정리합니다.
        """
        global kafka_consumer, kafka_listener_task
        
        logger.info("🛑 재난문자 리스너 종료 시작...")
        
        # 모든 SSE 클라이언트 연결 정리
        if connected_clients:
            logger.info(f"🔌 {len(connected_clients)}개의 SSE 연결 종료 중...")
            for client_queue in list(connected_clients.values()):
                try:
                    # 종료 신호 전송
                    await client_queue.put({"event": "shutdown"})
                except Exception as e:
                    logger.error(f"❌ 클라이언트 큐 정리 오류: {e}")
            connected_clients.clear()
            logger.info("✅ 모든 SSE 연결 종료됨")
        
        # Kafka consumer 종료
        if kafka_consumer is not None:
            try:
                logger.info("🔄 Kafka consumer 종료 중...")
                await kafka_consumer.stop()
                logger.info("✅ Kafka consumer 정상 종료됨")
            except Exception as e:
                logger.error(f"❌ Kafka 종료 오류: {e}")
        
        # 리스너 태스크 취소
        if kafka_listener_task is not None and not kafka_listener_task.done():
            kafka_listener_task.cancel()
            try:
                await kafka_listener_task
            except asyncio.CancelledError:
                logger.info("✅ Kafka 리스너 태스크 취소됨")
        
        logger.info("✅ 재난문자 리스너 종료 완료")
        
    @staticmethod
    async def generate_disaster_stream(user_id: str, request):
        """[수정됨] 사용자 지정석(Dictionary) 방식의 SSE 스트림"""
        
        logger.info(f"🔵 [SSE] generate_disaster_stream 시작 (user_id: {user_id})")
        
        # 🌟 1. 이미 내 이름(user_id)으로 된 기존 연결(유령)이 있다면 강제로 종료 신호를 보냅니다.
        if user_id in connected_clients:
            logger.info(f"🔄 [SSE] 중복 접속 감지! 기존 유령 연결을 밀어냅니다. (user_id: {user_id})")
            try:
                await connected_clients[user_id].put({"event": "shutdown"})
            except Exception:
                pass
                
        # 2. 새 바구니(큐)를 만들고, 내 전용 자리에 앉습니다.
        client_queue = asyncio.Queue()
        connected_clients[user_id] = client_queue
        logger.info(f"✅ [SSE] 클라이언트 연결됨 (현재 실제 접속자: {len(connected_clients)}명)")
        
        try:
            loop_count = 0
            while True:
                loop_count += 1
                
                # 사용자가 브라우저 창을 닫았는지 확인
                is_disconnected = await request.is_disconnected()
                if is_disconnected:
                    logger.info(f"👋 [SSE] 클라이언트 연결 종료 감지 (user_id: {user_id}, loop: {loop_count})")
                    break
                
                try:
                    disaster_data = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    
                    # 내 자리를 뺏은 새로운 접속자가 나에게 'shutdown'을 보냈다면 얌전히 물러납니다.
                    if isinstance(disaster_data, dict) and disaster_data.get("event") == "shutdown":
                        logger.info(f"🛑 [SSE] 새로고침으로 인해 이전 연결이 종료됩니다. (user_id: {user_id})")
                        break
                    
                    logger.info(f"📤 [SSE] 재난문자 전송 (user_id: {user_id})")
                    yield {
                        "event": "disaster",
                        "id": disaster_data["id"],
                        "data": disaster_data
                    }
                    
                except asyncio.TimeoutError:
                    # 1초마다 ping 전송 (연결 유지)
                    if loop_count % 10 == 1:  # 10초마다 한 번만 로그
                        logger.debug(f"🏓 [SSE] Ping 전송 (user_id: {user_id}, loop: {loop_count})")
                    yield {"event": "ping", "data": "keep-alive"}
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"❌ [SSE] 스트림 에러: {e}")
        finally:
            # 🌟 3. 내가 나갈 때, '내 자리에 있는 바구니'가 '지금 치우려는 이 바구니'가 맞을 때만 치웁니다.
            # (새로고침으로 인해 이미 새 바구니로 교체되었는데, 이전 바구니가 자리를 치워버리는 대참사 방지)
            if connected_clients.get(user_id) == client_queue:
                del connected_clients[user_id]
                logger.info(f"🔌 [SSE] 클라이언트 퇴장 완료 (남은 접속자: {len(connected_clients)}명)")
    