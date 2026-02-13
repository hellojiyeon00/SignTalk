# =========================================
# Model Server Setup Guide (Multi-Model)
# Python 3.9.x required
# AWS EC2 Ubuntu + GPU 기준
# =========================================

본 문서는 부트캠프 프로젝트의 model_server(멀티 모델 단일 FastAPI 서버) 운영 가이드이다.

지원 모델(예):
- KoBART (text -> gloss)
- LSTM
- FastText
- LLM

------------------------------------------
1. (권장) Python 버전 확인
------------------------------------------

    python --version

Python 3.9.x 가 아니면 아래 예시처럼 가상환경 생성

------------------------------------------
2. 가상환경 생성 및 활성화 (venv 예시)
------------------------------------------

    python3.9 -m venv venv
    source venv/bin/activate

------------------------------------------
3. PyTorch 설치 (GPU 환경)
------------------------------------------

[중요]
torch는 CUDA 버전에 맞춰 설치해야 한다.

1) CUDA 버전 확인

    nvidia-smi

2) 예: CUDA 11.6 환경이면(예시)

    pip install torch==1.12.0+cu116 \
      -f https://download.pytorch.org/whl/torch_stable.html

(환경에 맞는 버전으로 조정)

------------------------------------------
4. model_server requirements 설치
------------------------------------------

    pip install -r requirements.txt

추후 모델 확장 시(선택):
- FastText 사용 시: fasttext-wheel 추가 설치
- LLM 외부 API 호출 시: requests 추가 설치

------------------------------------------
5. 환경변수 설정 (.env 권장)
------------------------------------------

운영에서는 export 대신 .env 사용을 권장한다.

파일 위치:
- model_server/.env

예시(.env):

    # KoBART checkpoint 경로 (필수)
    KOBART_CHECKPOINT=/home/ubuntu/model_server/assets/kobart/checkpoint-17000

    # (선택) KoBART 모델명
    MODEL_NAME=kobart

    # (선택) 공통 device 힌트
    DEVICE=auto

    # (선택) KoBART generate 파라미터 (요청 payload로도 override 가능)
    MAX_NEW_TOKENS=64
    NUM_BEAMS=4

[중요]
- .env는 git에 올리지 말 것(.gitignore 포함)
- assets/ (모델 파일)도 git에 올리지 말 것

------------------------------------------
6. 모델 로딩 단독 테스트 (KoBART)
------------------------------------------

(주의) 아래 테스트는 KOBART_CHECKPOINT가 올바른 경로여야 한다.

    python - << 'EOF'
    import os
    from dotenv import load_dotenv
    load_dotenv()

    from model_server.models.kobart.loader import get_model_bundle
    bundle = get_model_bundle()
    print("device =", bundle["device"])
    print("model_name =", bundle["model_name"])
    print("model_dir =", bundle["model_dir"])
    EOF

------------------------------------------
7. 모델 서버 실행 (운영 모드)
------------------------------------------

단일 GPU 환경에서는 workers=1 권장.

    uvicorn main:app --host 0.0.0.0 --port 8001 --workers 1

(개발용) reload는 운영에서는 비권장

------------------------------------------
8. API Contract (Service ↔ Model Server)
------------------------------------------

Service 서버는 model_server의 /infer/{task}를 호출해 task에 맞는 추론을 수행한다.

[Endpoint]
- Method: POST
- Path: /infer/{task}
- Content-Type: application/json

task 예:
- kobart
- lstm
- fasttext
- llm

[Request (JSON)]
최소:

    {
      "text": "안녕하세요"
    }

옵션 파라미터는 payload에 전달:

    {
      "text": "안녕하세요",
      "payload": {
        "request_id": "optional-id",
        "top_k": 1,
        "max_new_tokens": 64,
        "num_beams": 4
      }
    }

[Response (200 OK)]
공통 래퍼 응답:

    {
      "ok": true,
      "task": "kobart",
      "result": {
        "request_id": "...",
        "input": "안녕하세요",
        "gloss": "....",
        "meta": {
          "model": "kobart",
          "latency_ms": 123,
          "device": "cuda"
        }
      }
    }

- result/meta는 task마다 형태가 달라질 수 있다.
- service는 meta가 없어도 정상 동작하도록 구현 권장.

------------------------------------------
9. Service-side error mapping (권장)
------------------------------------------

- timeout / connection error / model_server 5xx
  -> service는 502 Bad Gateway

- model_server 4xx (입력 문제, unknown task 등)
  -> service는 400 Bad Request (또는 정책에 따라 그대로 전달)

- response parsing 실패(schema mismatch)
  -> service는 502 Bad Gateway

------------------------------------------
10. Service Integration ENV (권장)
------------------------------------------

service는 model_server 주소를 환경변수로 주입한다.

    MODEL_SERVER_BASE_URL=http://127.0.0.1:8001
    MODEL_SERVER_TIMEOUT_SEC=10

------------------------------------------
(나중에 팀 README.md 하단부에 추가 예시)
------------------------------------------

## Model Server (Multi-Model)

This project includes a multi-model FastAPI model server for inference.

- Setup & run guide: docs/PRODUCTION.md
