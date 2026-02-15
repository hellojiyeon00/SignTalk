# 🚀 Model Server Setup Guide (Multi-Model)

> Python 3.9.x required  
> AWS EC2 Ubuntu + GPU 기준

본 문서는 **부트캠프 프로젝트의 model_server (멀티 모델 단일 FastAPI 서버)** 운영 가이드이다.

---

## 🧠 Supported Models

| Model      | Description |
|------------|------------|
| KoBART     | text → gloss |
| LSTM       | sequence model |
| FastText   | classification / embedding |
| LLM        | local or external API wrapper |

---

# 1️⃣ Python Environment

## Python 버전 확인

```bash
python --version
```

Python 3.9.x가 아니라면 가상환경 생성.

## 가상환경 생성 (venv)

```bash
python3.9 -m venv venv
source venv/bin/activate
```

---

# 2️⃣ PyTorch 설치 (GPU 환경)

> ⚠ torch는 CUDA 버전에 맞게 설치해야 한다.

## CUDA 버전 확인

```bash
nvidia-smi
```

## 예시 (CUDA 11.6)

```bash
pip install torch==1.12.0+cu116 \
  -f https://download.pytorch.org/whl/torch_stable.html
```

※ 반드시 서버 CUDA 환경에 맞춰 조정할 것.

---

# 3️⃣ Requirements 설치

```bash
pip install -r requirements.txt
```

추가 옵션:

- FastText 사용 시 → `fasttext-wheel`
- 외부 LLM API 호출 시 → `requests`

---

# 4️⃣ Environment Variables (.env 권장)

📂 위치:
```
model_server/.env
```

### 예시

```
KOBART_CHECKPOINT=/home/ubuntu/model_server/assets/kobart/checkpoint-17000
MODEL_NAME=kobart
DEVICE=auto
MAX_NEW_TOKENS=64
NUM_BEAMS=4
```

### 🔒 Important

- `.env`는 Git에 올리지 말 것
- `assets/` (모델 weight)도 Git에 올리지 말 것

---

# 5️⃣ KoBART 단독 로딩 테스트

```bash
python - << 'EOF'
from dotenv import load_dotenv
load_dotenv()

from model_server.models.kobart.loader import get_model_bundle
bundle = get_model_bundle()

print("device =", bundle["device"])
print("model_name =", bundle["model_name"])
print("model_dir =", bundle["model_dir"])
EOF
```

---

# 6️⃣ Server 실행 (Production)

> 단일 GPU 환경에서는 workers=1 권장

```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --workers 1
```

개발용:
```
--reload (운영 비권장)
```

---

# 7️⃣ API Contract (Service ↔ Model Server)

### Endpoint

| Method | Path | Content-Type |
|--------|------|--------------|
| POST   | /infer/{task} | application/json |

### Task 예시

```
kobart
lstm
fasttext
llm
```

---

## 📥 Request (Minimum)

```json
{
  "text": "안녕하세요"
}
```

## 📥 Request (With Options)

```json
{
  "text": "안녕하세요",
  "payload": {
    "request_id": "optional-id",
    "top_k": 1,
    "max_new_tokens": 64,
    "num_beams": 4
  }
}
```

---

## 📤 Response (200 OK)

```json
{
  "ok": true,
  "task": "kobart",
  "result": {
    "request_id": "...",
    "input": "안녕하세요",
    "gloss": "...",
    "meta": {
      "model": "kobart",
      "latency_ms": 123,
      "device": "cuda"
    }
  }
}
```

> result/meta는 task마다 달라질 수 있다.  
> service는 meta가 없어도 동작하도록 구현 권장.

---

# 8️⃣ Service Error Mapping (권장)

| 상황 | Service 응답 |
|------|--------------|
| timeout / connection error / 5xx | 502 Bad Gateway |
| model_server 4xx | 400 Bad Request |
| schema mismatch | 502 Bad Gateway |

---

# 9️⃣ Service Integration ENV

```
MODEL_SERVER_BASE_URL=http://127.0.0.1:8001
MODEL_SERVER_TIMEOUT_SEC=10
```

---

# 🔹 README 하단 추가 예시

```markdown
## Model Server (Multi-Model)

This project includes a multi-model FastAPI model server for inference.

- Setup & run guide: docs/PRODUCTION.md
```

---

## 📌 Architecture Note

본 구조는:

- Single Entry (`/infer/{task}`)
- Registry 기반 모델 분기
- 모델 1회 로드 후 재사용
- Service ↔ Model 완전 분리

를 전제로 설계되었다.
