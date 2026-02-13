# model_server (Production Guide)

부트캠프 프로젝트 운영용 멀티 모델 단일 FastAPI 서버

────────────────────────────────────────────

[운영 환경]

- AWS EC2 (Ubuntu)
- GPU 1개 (예: g4dn, g5 등)
- 단일 FastAPI 서버
- 모델 4종:
    - KoBART (GPU)
    - LSTM (CPU 또는 선택적 GPU)
    - FastText (CPU)
    - LLM (로컬 GPU 또는 외부 API)

────────────────────────────────────────────

[설계 원칙 - 운영 기준]

1. 단일 프로세스 운영
   - uvicorn 1 worker 권장
   - GPU 모델은 단일 프로세스에서 관리

2. Lazy Loading 전략
   - 서버 시작 시 모든 모델을 preload하지 않음
   - 최초 요청 시 load()
   - 이후 전역 캐시 유지

3. GPU 메모리 보호 전략
   - KoBART 우선 GPU
   - FastText는 CPU 고정
   - LSTM은 CPU 기본
   - LLM은 가능하면 외부 API 권장
   - 로컬 LLM 사용 시 메모리 사용량 반드시 확인

────────────────────────────────────────────

[폴더 구조]

model_server/

  main.py
    - FastAPI 엔트리
    - POST /infer/{task}

  registry.py
    - task → handler 매핑

  models/
    kobart.py
    lstm.py
    fasttext.py
    llm.py

  assets/
    kobart/
    lstm/
    fasttext/
    llm/

  requirements.txt
  README.md

────────────────────────────────────────────

[실행 방법 - 운영 모드]

1. 가상환경 활성화

   source venv/bin/activate

2. 의존성 설치

   pip install -r requirements.txt

3. GPU 확인

   nvidia-smi

4. 서버 실행 (운영용)

   uvicorn main:app \
       --host 0.0.0.0 \
       --port 8001 \
       --workers 1

※ --reload 사용 금지 (운영 환경)

────────────────────────────────────────────

[환경 변수 권장 설정]

MODEL_BASE_PATH=/home/ubuntu/model_server/assets
DEVICE=cuda
LOG_LEVEL=info

예시 실행:

DEVICE=cuda uvicorn main:app --host 0.0.0.0 --port 8001

────────────────────────────────────────────

[GPU 운영 전략]

1. 서버 시작 시 모델을 모두 GPU에 올리지 말 것
2. load() 내부에서 다음과 같이 처리 권장:

   - if DEVICE == "cuda":
         model.to("cuda")

3. 사용하지 않는 모델은 GPU에 올리지 않기
4. CUDA OOM 발생 시:
   - LLM 분리 고려
   - LSTM을 CPU로 고정
   - batch size 감소

────────────────────────────────────────────

[성능 고려 사항]

- KoBART 추론은 GPU 필수
- FastText는 CPU에서도 ms 단위 응답
- LLM은 가장 무거움
- 동시 요청이 많을 경우:
    - 단일 worker 구조에서는 직렬 처리됨
    - 추후 gunicorn + uvicorn worker 구조 고려 가능

────────────────────────────────────────────

[장애 대응 체크리스트]

1. 서버 다운 시:
   - journalctl -u 서비스명 확인
   - uvicorn 로그 확인

2. GPU 오류 시:
   - nvidia-smi 확인
   - CUDA OOM 여부 확인

3. 모델 경로 오류:
   - assets 폴더 경로 확인
   - checkpoint 존재 여부 확인

────────────────────────────────────────────

[보안 권장 사항]

- EC2 보안 그룹에서 8001 포트 제한
- 내부 통신 전용이면 0.0.0.0 대신 내부 IP 바인딩 고려
- LLM 외부 API 사용 시 API Key는 .env로 관리

────────────────────────────────────────────

[운영 결론]

- 단일 GPU EC2에서는
    KoBART 중심 구조로 운영
- FastText는 CPU
- LLM은 외부 API 권장
- 모델 로딩은 Lazy Loading
- uvicorn worker 1개 유지

────────────────────────────────────────────

부트캠프 프로젝트 운영용 model_server 가이드
