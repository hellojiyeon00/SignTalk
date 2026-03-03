# ── hadoop/Dockerfile ───────────────────────────────────────────
# 빌드 컨텍스트: 프로젝트 루트 (.)
# 역할: HDFS REST 게이트웨이
FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 서비스 전용 requirements 설치
COPY hadoop/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사 (hadoop_app 패키지만)
COPY hadoop/hadoop_app ./hadoop_app

CMD ["uvicorn", "hadoop_app.main:app", "--host", "0.0.0.0", "--port", "8003"]
