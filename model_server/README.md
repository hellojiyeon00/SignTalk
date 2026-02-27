# 🚀 Model Server (Inference Only)

부트캠프 프로젝트의 **모델 전용 추론 서버**입니다.  
FastAPI 기반 단일 엔트리 구조이며, Service Layer와 완전히 분리되어 있습니다.

---

# 🧠 Architecture Overview

- Single Entry Point: `POST /infer/{task}`
- Registry 기반 모델 분기
- 모델 Lazy Loading (최초 요청 시 로드)
- GPU 메모리 보호 전략 적용
- Service ↔ Model 완전 분리

---

# 📁 Directory Structure

    model_server/
    │
    ├── main.py
    │   # FastAPI 엔트리 포인트
    │   # POST /infer/{task} 라우팅 담당
    │   # 요청/응답 공통 스키마 처리
    │
    ├── registry.py
    │   # task → handler 매핑 테이블
    │   # 모델 추가 시 이 파일만 수정
    │
    ├── models/
    │   # 모델 로직 모듈 디렉토리
    │   │
    │   ├── kobart/
    │   │   ├── loader.py        # KoBART 모델/토크나이저 로드
    │   │   ├── infer.py         # text → gloss 추론
    │   │   └── preprocess.py    # 전처리/후처리
    │   │
    │   └── fasttext/
    │       ├── loader.py        # fastText 모델 로드
    │       ├── recommend.py     # 유사 단어 추천 로직
    │       └── ...
    │
    ├── assets/
    │   # 모델 weight 저장 디렉토리 (Git 추적 제외)
    │   │
    │   ├── kobart/              # KoBART checkpoint
    │   └── fasttext/            # fastText .bin 파일
    │
    ├── ops/
    │   # 운영 관련 디렉토리
    │   │
    │   ├── run/                 # 서버 실행 스크립트
    │   ├── logs/                # 로그 파일 저장 위치
    │   └── pids/                # 프로세스 PID 관리
    │
    ├── requirements.txt         # Python 의존성
    └── README.md                # 현재 문서

---

# 🐍 Development Environment

- Python 3.9.x
- Conda 환경 사용

## 1️⃣ Conda 환경 생성

    conda create -n model_server python=3.9
    conda activate model_server

---

## 2️⃣ PyTorch 설치 (GPU 환경 예시: CUDA 11.6)

    pip install torch==1.12.0+cu116 \
      -f https://download.pytorch.org/whl/torch_stable.html

⚠ 반드시 서버 CUDA 버전에 맞게 설치할 것.

CUDA 확인:

    nvidia-smi

---

## 3️⃣ Requirements 설치

    pip install -r requirements.txt

---

# 📦 requirements.txt (Inference 전용)

    # Deep Learning
    torch==1.12.0+cu116
    transformers==4.26.1
    sentencepiece
    numpy==1.26.4
    PyYAML

    # API Server
    fastapi
    uvicorn
    httpx

※ fastText DB 기반 추천을 위해 SQLAlchemy가 포함됨.

---

# ⚙️ Environment Variables (.env 권장)

위치:

    프로젝트 루트의 .env 파일 사용
    model_server는 별도의 .env를 사용하지 않으며,
    루트 .env를 통해 환경변수를 로드한다.

예시:

    DATABASE_URL=postgresql://multicampus_user:multicampuscci4@56.155.47.51:5432/multicampus_db
    
    FASTTEXT_MODEL_PATH=/home/lab06/SignTalk/model_server/assets/fasttext/cc.ko.300.bin

    KOBART_CHECKPOINT=/home/lab06/SignTalk/model_server/assets/kobart/final_model_checkpoint-17800
    
    DEVICE=auto
    MAX_NEW_TOKENS=64
    NUM_BEAMS=4

⚠ `.env`와 `assets/`는 Git에 올리지 말 것.

---

# 🚀 Server 실행

## Production (권장)
    
프로젝트 루트에서 실행:

    uvicorn model_server.main:app \
        --host 0.0.0.0 \
        --port 8001 \
        --workers 1

⚠ GPU 환경에서는 workers=1 유지 권장  
⚠ 운영 환경에서 --reload 사용 금지

---

# 📡 API Contract

## Endpoint

    POST /infer/{task}

## Supported Task

- kobart
- fasttext

---

## 📥 Request (Minimum)

    {
      "text": "안녕하세요"
    }

## 📥 Request (With Options)

    {
      "text": "안녕하세요",
      "payload": {
        "top_k": 1,
        "max_new_tokens": 64,
        "num_beams": 4
      }
    }

---

## 📤 Response (Example)

    {
      "ok": true,
      "task": "kobart",
      "result": {
        "gloss": "...",
        "meta": {
          "latency_ms": 123,
          "device": "cuda"
        }
      }
    }

---

# 🧠 Production Design Principles

## 1️⃣ Single Process

- uvicorn worker 1개 유지
- GPU 모델은 단일 프로세스에서 관리

## 2️⃣ Lazy Loading

- 서버 시작 시 모든 모델 preload ❌
- 최초 요청 시 load()
- 이후 전역 캐시 유지

## 3️⃣ GPU 전략

- KoBART → GPU 우선
- FastText → CPU 고정
- CUDA OOM 발생 시:
  - batch 감소
  - LLM 분리
  - CPU fallback 고려

---

# 🔐 Security

- EC2 보안 그룹에서 8001 포트 제한
- 내부 통신 전용이면 내부 IP 바인딩 고려
- API Key는 반드시 `.env`로 관리

---

# 🏁 Summary

본 Model Server는:

- 멀티 모델 단일 엔트리 구조
- Lazy Loading 기반
- GPU 메모리 보호 전략 적용
- Service Layer와 완전 분리

를 목표로 설계된 **Inference 전용 FastAPI 서버**입니다.