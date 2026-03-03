# ── backend/Dockerfile ──────────────────────────────────────────
# 빌드 컨텍스트: 프로젝트 루트 (.)
FROM python:3.9-slim

WORKDIR /app

# 시스템 의존성 (psycopg2-binary 런타임)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# 서비스 전용 requirements 설치
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY backend/app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
