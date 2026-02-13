model_server/
│
├── main.py
│   # FastAPI 엔트리
│   # POST /infer/{task}
│   # task 문자열만 보고 아래 registry에서 핸들러 호출
│   #
│   # 예) task: "kobart" | "lstm" | "fasttext" | "llm"
│
├── registry.py
│   # task → handler 함수 매핑 테이블(딱 이거만)
│   # 예) HANDLERS = {"kobart": kobart.infer, "lstm": lstm.infer, ...}
│   # 모델 추가/삭제 시 여기만 건드리면 됨
│
├── models/
│   ├── kobart.py
│   │   # KoBART 로드(체크포인트/토크나이저)
│   │   # infer(text) -> gloss(str or tokens)
│   │   # 전역 캐시로 1회 로드(프로세스 내)
│   │
│   ├── lstm.py
│   │   # LSTM 로드(.pt/.pth)
│   │   # infer(input) -> output
│   │
│   ├── fasttext.py
│   │   # FastText 모델 로드(.bin)
│   │   # infer(text) -> (label/score or embedding)
│   │
│   └── llm.py
│       # LLM 호출 래퍼
│       # - 내부에 LLM이 뜨는 구조면: 로드 + infer
│       # - 외부 API 호출이면: 요청/응답 파싱 + timeout/retry
│
├── assets/
│   ├── kobart/        # KoBART checkpoint 디렉토리(예: checkpoint-17000/)
│   ├── lstm/          # LSTM weight 파일(.pt/.pth)
│   ├── fasttext/      # fastText .bin
│   └── llm/           # (선택) 로컬 LLM weight or prompt 템플릿 등
│
└── requirements.txt
    # fastapi, uvicorn, torch, transformers, fasttext(또는 gensim/fasttext-wheel), ...
