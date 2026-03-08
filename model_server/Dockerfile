# ── model_server/Dockerfile ─────────────────────────────────────
# 빌드 컨텍스트: 프로젝트 루트 (.)
# 역할: KoBART (text→gloss) + FastText (단어 추천) 추론 서버
FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
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

# 4) 시작 스크립트 복사 및 실행 권한 부여
RUN chmod +x /app/model_server/start.sh

# 모델 파일은 docker-compose 볼륨으로 주입
# - ./model_server/assets:/app/assets:ro
#   ├── kobart/final_model_checkpoint-17800/
#   └── fasttext/cc.ko.300.bin

CMD ["/app/model_server/start.sh"]
