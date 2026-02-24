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

# FastAPI 백그라운드와 사용자 프론트엔드(SSE) 사이에서 데이터를 임시 보관할 비동기 큐(대기열)입니다.
disaster_queue = asyncio.Queue()

class DisasterService:
    
    @staticmethod
    async def start_disaster_listener():
        """
        [Kafka 리스너 함수]
        FastAPI 서버가 켜질 때 백그라운드에서 무한히 실행되며, 
        Kafka 우체통(Topic)에 새 재난문자가 오는지 24시간 감시합니다.
        """
        # Kafka가 비활성화되어 있으면 리스너를 시작하지 않음
        if not settings.KAFKA_ENABLED:
            logger.warning("⚠️ Kafka가 비활성화되어 있습니다. (.env에서 KAFKA_ENABLED=true로 설정하세요)")
            logger.info("💡 재난문자를 받으려면 Kafka 서버 설정을 확인하고 KAFKA_ENABLED=true로 변경하세요.")
            return
        
        retry_count = 0
        max_retries = 3  # 최대 재시도 횟수
        
        while True:  # 연결 실패 시 재시도를 위한 외부 루프
            consumer = None
            try:
                # 1. Kafka 우체국에서 데이터를 꺼내올 '구독자(Consumer)' 객체를 만듭니다.
                consumer = AIOKafkaConsumer(
                    'Topic_characters',                     # 창주님이 만든 Kafka 우체통(토픽) 이름입니다.
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,     # Kafka 서버의 주소와 포트입니다.
                    group_id='disaster_consumer_group',     # 컨슈머 그룹 ID (필수) - 같은 그룹은 메시지를 나눠서 받습니다.
                    # 받은 데이터는 010101 같은 바이트(Byte) 형태이므로, 이를 파이썬 딕셔너리(JSON)로 자동 번역해 주는 기능입니다.
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')), 
                    auto_offset_reset='latest',             # 서버가 켜진 '지금 이 순간 이후'에 도착하는 새 문자만 받겠다는 뜻입니다.
                    enable_auto_commit=True,                # 메시지를 읽었다는 처리(오프셋 커밋)를 자동으로 합니다.
                    request_timeout_ms=30000,               # 요청 타임아웃 30초
                    connections_max_idle_ms=540000          # 연결 유지 시간 9분
                )
                
                # 2. Kafka 서버와 연결을 시작합니다 (타임아웃 10초)
                await asyncio.wait_for(consumer.start(), timeout=10.0)
                logger.info(f"✅ Kafka 연결됨")
                retry_count = 0  # 연결 성공 시 재시도 카운터 초기화

                # 3. 무한 루프를 돌며 우체통에 편지가 들어올 때까지 문 앞에서 대기합니다.
                async for msg in consumer:
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
                            "region": data.get("disaster_rcptn_rgn_nm", ""),      # 발생 지역 (예: 서울특별시 강남구)
                            "time": now_kst                                       # 받은 시간
                        }
                        
                        # 6. 포장된 데이터를 FastAPI 내부의 배달 큐(대기열)에 밀어 넣습니다.
                        await disaster_queue.put(disaster_data)
                        logger.info(f"🚨 [Kafka] {disaster_data['type_code']} [{disaster_data['region']}] {disaster_data['message'][:30]}...")
                        
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
                if consumer is not None:
                    try:
                        await consumer.stop()
                    except Exception as e:
                        logger.error(f"❌ Kafka 종료 중 오류: {e}")
    
    @staticmethod
    async def generate_disaster_stream(user_id: str, request):
        """
        [SSE 실시간 전송기]
        위의 리스너가 disaster_queue에 데이터를 밀어 넣으면, 
        이 함수가 쏙 빼서 현재 접속 중인 사용자의 브라우저로 발사(yield)합니다.
        """
        try:
            while True:
                # 사용자가 브라우저 창을 닫았는지 확인합니다. 닫았다면 전송 루프를 멈춥니다.
                if await request.is_disconnected():
                    break
                
                try:
                    # 대기열(큐)에 데이터가 들어올 때까지 최대 1초간 기다리며 꺼내봅니다.
                    disaster_data = await asyncio.wait_for(disaster_queue.get(), timeout=1.0)
                    
                    # 데이터가 있다면 프론트엔드(chat.js)로 쏴줍니다! (이 yield가 핵심입니다)
                    yield {
                        "event": "disaster",
                        "id": disaster_data["id"],
                        "data": disaster_data
                    }
                    
                except asyncio.TimeoutError:
                    # 1초 동안 대기열에 아무 재난문자도 안 들어왔다면, 
                    # 브라우저가 "서버 죽었나?" 하고 오해하지 않도록 빈 심장박동(ping)만 보냅니다.
                    yield {"event": "ping", "data": "keep-alive"}
                    
        except Exception as e:
            logger.error(f"❌ [SSE] 스트림 전송 중 에러: {e}")