# ================================
# KoBART Model Server Setup Guide
# Python 3.9.x required
# ================================

# 1. (권장) Python 버전 확인
python --version
# Python 3.9.x 가 아니면 아래 예시처럼 가상환경 생성

# 2. 가상환경 생성 및 활성화 (venv 예시)
python3.9 -m venv venv
source venv/bin/activate

# ----------------
# PyTorch 설치
# ----------------

# [A] CPU 환경 (기본 / 가장 안전)
pip install torch==1.12.0+cpu \
  -f https://download.pytorch.org/whl/torch_stable.html

# [B] GPU 환경 (CUDA 11.6 예시)
# pip install torch==1.12.0+cu116 \
#   -f https://download.pytorch.org/whl/torch_stable.html

# ----------------
# KoBART inference requirements 설치
# ----------------
pip install -r requirements/kobart_infer.txt

# ----------------
# (선택) 학습까지 필요한 경우
# ----------------
# pip install -r requirements/kobart_train.txt

# ----------------
# 환경변수 설정 (모델 경로)
# ----------------
export KOBART_MODEL_DIR="models/kobart/final_model_checkpoint-17800"
export DEVICE="cpu"          # gpu 서버면 cuda
export MAX_NEW_TOKENS="64"
export NUM_BEAMS="4"

# ----------------
# 모델 로딩 단독 테스트
# ----------------
python - << 'EOF'
from model_server.services.kobart_infer import KoBARTInfer
engine = KoBARTInfer()
res = engine.infer("안녕하세요")
print(res.gloss)
print(res.meta)
EOF

# ----------------
# 모델 서버 실행
# ----------------
uvicorn model_server.app:app --host 0.0.0.0 --port 8001

(나중에 기존 팀 README.md 하단부에 내용 추가)
---

## Model Server (KoBART)

This project includes a KoBART-based model server for Korean text-to-gloss inference.

- Setup & run guide: [`docs/model_server.md`](docs/model_server.md)

---

## API Contract (Service ↔ Model Server)

Service 서버는 model_server의 `/v1/translate`를 호출해 텍스트를 gloss로 변환한다.

### Endpoint
- Method: POST
- Path: /v1/translate
- Content-Type: application/json

### Request (JSON)
    {
      "text": "안녕하세요"
    }

### Response (200 OK)
    {
      "gloss": "지시1 지시1# 안녕하세요1",
      "meta": {
        "model": "kobart",
        "checkpoint": "checkpoint-17000"
      }
    }

- meta는 optional이며, service는 없어도 정상 동작해야 한다.

### Service-side error mapping (권장)
- timeout / connection error / model_server 5xx → service는 502 Bad Gateway
- model_server 4xx (입력 문제 등) → service는 400 Bad Request (또는 정책에 따라 그대로 전달)
- response parsing 실패(schema mismatch) → service는 502 Bad Gateway

---

## Service Integration ENV

service는 model_server 주소를 환경변수로 주입한다.

    MODEL_SERVER_BASE_URL=http://127.0.0.1:8001
    MODEL_SERVER_TIMEOUT_SEC=10

