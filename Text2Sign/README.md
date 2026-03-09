# 🚀 Model Server (Inference Only)

부트캠프 프로젝트의 모델 전용 추론 서버입니다.  
FastAPI 기반 단일 엔트리 구조이며 Backend Service Layer와 완전히 분리되어 있습니다.

---

# 🧠 Architecture Overview

- Single Entry Point: POST /infer/{task}
- Registry 기반 모델 분기
- Model Registry Pattern 적용
- KoBART Lazy Loading
- FastText Startup Warmup
- FastText + pgvector Retrieval Pipeline
- Backend ↔ Text2Sign (model_server) 완전 분리

---

# 📁 Directory Structure

```
Text2Sign/
│
├── main.py
│   FastAPI 엔트리 포인트
│   POST /infer/{task} 라우팅 담당
│
├── registry.py
│   task → handler 매핑 테이블
│   모델 추가 시 이 파일만 수정
│
├── models/
│   모델 로직 모듈 디렉토리
│
│   ├── kobart/
│   │   ├── __init__.py
│   │   │   KoBART 추론 엔트리
│   │   │   registry.py에서 kobart.infer 호출
│   │   │   요청 파라미터 처리 및 generate_gloss 실행
│   │   │
│   │   ├── loader.py
│   │   │   KoBART 모델 로드 / Lazy Load
│   │   │
│   │   └── generate.py
│   │       gloss 생성 로직
│   │
│   └── fasttext/
│       ├── __init__.py
│       │   fasttext 모듈 패키지 선언
│       │
│       ├── loader.py
│       │   fastText 모델 로드
│       │
│       ├── recommend.py
│       │   유사 단어 추천 로직
│       │
│       └── ...
│
├── utils/
│   └── jsonl_logger.py
│       추론 로그 JSONL 저장 유틸
│       성능 분석 및 디버깅 로그 기록
│
├── assets/
│   모델 weight 저장 디렉토리 (Git 추적 제외)
│
│   ├── kobart/
│   └── fasttext/
│
└── README.md
```

---

# 🐍 Development Environment

- Python 3.9.x (고정)
- Conda 환경 사용
- EC2 Ubuntu + CUDA 환경 기준

⚠ 본 프로젝트는 Python 3.9 환경을 기준으로 합니다.

---

# 1️⃣ Conda 환경 생성

```
conda create -n SignTalk python=3.9 -y
conda activate SignTalk
```

---

# 2️⃣ pip 최신화

```
python -m pip install -U pip
```

---

# 3️⃣ Requirements 설치

Model Server는 **프로젝트 루트 requirements.txt를 사용합니다.**

```
pip install -r requirements.txt
```

---

# 🔥 PyTorch + CUDA 정책

현재 표준 환경

- Python 3.9
- CUDA 12.4
- torch 2.6.0 + cu124

루트 requirements.txt에는 다음 인덱스가 포함되어 있어야 합니다.

```
--extra-index-url https://download.pytorch.org/whl/cu124
```

설치 확인

```
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

정상 출력 예

```
2.6.0+cu124 True
```

---

# ⚙️ Environment Variables (.env)

Model Server는 **프로젝트 루트 .env 파일을 사용합니다.**

⚠ `.env`와 `assets/`는 Git에 업로드하지 않습니다.

---

# 🚀 Text2Sign (Model Server) 실행

⚠ 실행 스크립트는 **프로젝트 루트에 위치합니다**

권장 실행 (warmup 포함)

```
chmod +x start_text2sign_server.sh
./start_text2sign_server.sh
```

해당 스크립트는

- FastText 모델 preload
- KoBART 모델 warmup
- FastText corpus cache warmup

을 자동 수행하여 **Cold Start 지연을 방지합니다.**

수동 실행 (warmup 없이)

```
uvicorn Text2Sign.main:app \
    --host 0.0.0.0 \
    --port 8953
```

⚠ 운영 환경에서 `--reload` 사용 금지

---

# 📡 API Contract

Endpoint

```
POST /infer/{task}
```

지원 Task

```
kobart
fasttext
```

Request (Minimum)

```json
{
  "text": "안녕하세요"
}
```

Request (Options)

```json
{
  "text": "안녕하세요",
  "payload": {
    "top_k": 1,
    "max_new_tokens": 64,
    "num_beams": 4
  }
}
```

Response Example

```json
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
```

---

# 🧠 Model Loading Strategy

KoBART

- Lazy Load
- 최초 요청 시 모델 로드
- 이후 전역 캐시 유지

FastText

- Server Startup Warmup
- 서버 시작 시 모델 preload
- corpus cache warmup 수행

Cold Start

```
FastText 최초 로딩: 약 60~70초
Warmup 이후: 약 60~80ms
KoBART 추론: 약 350~500ms
```

---

# 🔎 FastText Retrieval Pipeline

```
# 🔎 FastText Retrieval Pipeline

1. Input Text
2. Tokenize
3. FastText Word Vector 생성
4. pgvector Similarity Search
5. Top-K Corpus Match
6. Word → Sign Video URL Mapping
```

---

# 📊 Performance Logging

```
[fasttext][pgvector][timing]
[fasttext][count]
[fasttext.infer][timing]
```

예시

```
[fasttext][pgvector][timing] token=햄버거 dim=300 connect_ms=18 query_ms=4 rows=10
```

```
[fasttext][count] tokens_len=3 unique_tokens=3 top_k=10 pgvector_queries=3 recommend_calls=2 elapsed_ms=82
```

```
[fasttext.infer][timing] bundle_ms=0 prep_ms=0 recommend_ms=82 total_ms=82
```

---

# 🔐 Security

- EC2 보안 그룹에서 8953 포트 제한
- 내부 서비스 전용일 경우 Private IP 바인딩 권장
- 민감 정보는 `.env`로 관리

---

# 🚀 SignTalk 서버 실행 및 확인

## 1️⃣ Text2Sign (Model Server)

### 실행

```
./start_text2sign_server.sh
```

### 접속 확인

http://56.155.47.51:8953/docs

---

## 2️⃣ Backend Server

### 실행

```
cd Backend
uvicorn app.main:app --host 0.0.0.0 --port 8951
```

### 접속 확인

http://56.155.47.51:8951/docs

---

# 🔗 전체 서버 구조

| Component | Address                  |
| --------- | ------------------------ |
| Text2Sign | http://56.155.47.51:8953 |
| Backend   | http://56.155.47.51:8951 |

---

# ⚡ 서버 실행 순서 (권장)

1. **Text2Sign (Model Server) 실행**
2. **Backend Server 실행**

---

## 5️⃣ 채팅 동작 흐름

```
Frontend
   ↓ socket emit
Backend (8951)
   ↓ HTTP 요청 (/infer/*)
Text2Sign (8953)
   ↓ 결과 반환
Backend
   ↓ socket broadcast
Frontend
   ↓
채팅 메시지 + 수어 영상 표시
```

---

# 🏁 Summary

본 Text2Sign은

- FastAPI 기반 Inference Server
- 멀티 모델 단일 엔트리 구조
- KoBART Lazy Loading
- FastText Startup Warmup
- FastText + pgvector Retrieval Pipeline
- JSONL 기반 추론 로그 기록
- Python 3.9 + CUDA 환경 고정

을 기반으로 설계된 **Inference 전용 Model Server**입니다.