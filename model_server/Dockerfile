# ── model_server/Dockerfile ─────────────────────────────────────
# 빌드 컨텍스트: 프로젝트 루트 (.)
# 역할: KoBART (text→gloss) + FastText (단어 추천) 추론 서버
FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 1) CPU 전용 PyTorch (CUDA 패키지 대체)
# --extra-index-url 추가: typing-extensions 등 의존성을 PyPI에서 보완
RUN pip install --no-cache-dir \
    torch==2.6.0 \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple

# 2) 서비스 전용 requirements 설치
COPY model_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) 소스 복사 (model_server 패키지만)
COPY model_server ./model_server

# 모델 파일은 docker-compose 볼륨으로 주입
# - ./model_server/assets:/app/assets:ro
#   ├── kobart/final_model_checkpoint-17800/
#   └── fasttext/cc.ko.300.bin

CMD ["uvicorn", "model_server.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]
