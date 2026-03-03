# ── model/Dockerfile ────────────────────────────────────────────
# 빌드 컨텍스트: 프로젝트 루트 (.)
# 역할: LSTM 수어 인식 서버
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
COPY model/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) 소스 복사 (model_app 패키지만)
COPY model/model_app ./model_app

# 모델 파일은 docker-compose 볼륨으로 주입
# - ./model/LSTM:/app/model/LSTM:ro

CMD ["uvicorn", "model_app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
