# 📦 Model Server 구조

`model_server/`는 멀티 모델 단일 엔트리 구조로 설계되어 있습니다.  
FastAPI 하나로 여러 모델을 task 기반으로 분기 처리합니다.

---

## 📁 Directory Structure

```
model_server/
│
├── main.py
│   # FastAPI 엔트리
│   # POST /infer/{task}
│   # task 문자열만 보고 registry에서 핸들러 호출
│   #
│   # 예) task: "kobart" | "lstm" | "fasttext" | "llm"
│
├── registry.py
│   # task → handler 함수 매핑 테이블
│   # 예) HANDLERS = {"kobart": kobart.infer, "lstm": lstm.infer, ...}
│   # 모델 추가/삭제 시 이 파일만 수정하면 됨
│
├── models/
│   ├── kobart.py
│   │   # KoBART 로드 (체크포인트 / 토크나이저)
│   │   # infer(text) -> gloss(str or tokens)
│   │   # 전역 캐시로 1회 로드 (프로세스 내)
│   │
│   ├── lstm.py
│   │   # LSTM 로드 (.pt / .pth)
│   │   # infer(input) -> output
│   │
│   ├── fasttext.py
│   │   # FastText 모델 로드 (.bin)
│   │   # infer(text) -> (label / score or embedding)
│   │
│   └── llm.py
│       # LLM 호출 래퍼
│       # - 내부에 LLM이 뜨는 구조면: 로드 + infer
│       # - 외부 API 호출이면: 요청/응답 파싱 + timeout/retry
│
├── assets/
│   ├── kobart/        # KoBART checkpoint 디렉토리 (예: checkpoint-17000/)
│   ├── lstm/          # LSTM weight 파일 (.pt / .pth)
│   ├── fasttext/      # fastText .bin 파일
│   └── llm/           # (선택) 로컬 LLM weight 또는 prompt 템플릿 등
│
└── requirements.txt
    # fastapi
    # uvicorn
    # torch
    # transformers
    # fasttext (또는 gensim / fasttext-wheel)
    # 기타 의존성
```

---

## 🧠 설계 철학

- **Single Entry Point**
  - 모든 모델 호출은 `/infer/{task}` 하나로 통일
- **Registry 기반 분기**
  - 모델 추가 시 `models/`에 파일 추가
  - `registry.py`에 핸들러 등록만 하면 확장 완료
- **모델 1회 로드**
  - 프로세스 시작 시 1회 로드 → 재요청 시 재사용
- **모듈 단위 독립성**
  - 각 모델 파일은 `infer()` 인터페이스만 맞추면 됨

---

## 🚀 API 예시

```
POST /infer/kobart
{
  "text": "안녕하세요"
}
```

```
POST /infer/lstm
{
  "payload": {...}
}
```

---

## ✅ 모델 추가 방법

1. `models/new_model.py` 생성
2. `infer()` 함수 구현
3. `registry.py`에 핸들러 등록

```python
HANDLERS = {
    "kobart": kobart.infer,
    "lstm": lstm.infer,
    "fasttext": fasttext.infer,
    "llm": llm.infer,
    "new_model": new_model.infer,
}
```

---

이 구조는  
**멀티 모델 환경에서 유지보수성과 확장성을 극대화하기 위한 설계**입니다.
