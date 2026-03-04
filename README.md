# 🖐️ 수어·텍스트 변환 SNS 서비스

---

## 🗓️ 프로젝트 기간

2026년 01월 12일 ~ 2026년 03월 11일

## 👥 팀명

**SignLanguageTalk**

## 🧑‍💻 팀원

- 안호용 👑
- 강지연
- 김소영
- 이창주

---

## 1. 📘 프로젝트 개요

수어는 한국어와는 다른 **독립적인 언어 체계**를 가진 언어로, 많은 농인(聾人) 사용자들이 한글 기반의 SNS를 이용하는 데 어려움을 겪고 있습니다.

본 프로젝트는 **한글을 읽고 쓰는 데 어려움이 있는 농인**을 위해, **한국수어 ↔ 한글 텍스트를 실시간으로 변환**하여 소통할 수 있는 SNS 서비스를 개발하는 것을 목표로 합니다.

농인과 일반인이 동일한 SNS 환경에서 장벽 없이 소통할 수 있도록, AI 기반 수어 인식·생성 기술과 실시간 메시징 기능을 결합한 **포용적 커뮤니케이션 플랫폼**을 구현합니다.

---

## 2. 🧩 서비스 설명

### 농인 → 일반인 (수어 → 텍스트)

- 농인 사용자가 입력한 수어 영상을 프레임 단위로 입력받아 **랜드마크 추출**
- 고정된 프레임의 랜드마크를 학습된 모델에 입력하여 **글로스(수어 단어)로 분류**
- 반환된 글로스(수어 단어) 리스트를 **LLM 모델에 입력**하여 하나의 문장으로 변환 
- 변환된 문장을 SNS 메시지 형태로 일반 사용자에게 전송

### 일반인 → 농인 (텍스트 → 수어 영상)

- 일반 사용자가 입력한 한글 텍스트 메시지를 학습된 모델에 입력하여 **글로스(수어 단어) 단위로 분리**
- 각 글로스(수어 단어)에 해당하는 **수어 영상을 매핑**
- 반환된 **수어 영상을 순차적으로 연결**하여 농인 사용자에게 전송

### 재난 안내 수어 알림 서비스

- GPS 기반 사용자 위치 탐지
- 사용자 위치와 연관된 **재난 안내 문자 자동 수신**
- 재난 문자 텍스트를 **수어 영상으로 변환**
- 텍스트 + 수어 영상을 함께 제공하여 정보 접근성 강화

---

## 3. 🗂️ 데이터 구성

- [모두의 말뭉치](https://kli.korean.go.kr/corpus/main/requestMain.do) **한국어-한국수어 병렬 말뭉치 2024**
- [문화공공데이터광장](https://www.culture.go.kr/data/openapi/openapiView.do?id=367&keyword=%EC%9D%BC%EC%83%81%EC%83%9D%ED%99%9C%EC%88%98%EC%96%B4&searchField=all&gubun=A)
    - **국립국어원_일상생활수어 오픈 API**
    - **국립국어원_문화정보수어 오픈 API**
    - **국립국어원_전문용어수어 오픈 API**
- [재난안전데이터공유플랫폼](https://www.safetydata.go.kr/disaster-data/view?dataSn=228#none) **행정안전부_긴급재난문자 오픈 API**

---

## 4. 🧹 데이터 전처리

### 🎥 수어 영상 전처리

- MediaPipe를 활용한 관절(Keypoint) 추출
- 프레임 복제 및 샘플링

### 📝 텍스트 전처리

- 특수문자 및 불필요 기호 제거
- 형태소 단위 토큰화
- 수어 문법에 맞는 문장 재구성

---

## 5. 🛠️ 주요 기술 스택

### ✔ AI / Modeling

- PyTorch
- LSTM
- Gemini API
- MediaPipe
- KoBART
- FastText

### ✔ Backend

- FastAPI
- Nginx
- Docker / Docker Compose

### ✔ Frontend

- HTML5
- JavaScript

### ✔ Data Engineering

- Hadoop
- Apache Spark
- Apache Kafka
- Apache Airflow

### ✔ Database

- PostgreSQL
- Redis

---

## 6. 📁 프로젝트 구조

```
SignLanguageTalk/
│
├── backend/               # FastAPI 백엔드
│   └── app/
│       ├── api/           # API 엔드포인트
│       ├── core/          # 설정, DB, Redis 연결
│       ├── models/        # SQLAlchemy ORM 모델
│       └── services/      # 비즈니스 로직 (AI 변환, 재난문자 등)
│
├── frontend/              # HTML/JS 프론트엔드
│   ├── assets/            # CSS
│   ├── js/                # JavaScript 로직
│   └── *.html
│
├── model/                 # Model App — LSTM 수어 인식 (FastAPI)
│   ├── model_app/         # FastAPI 앱
│   └── LSTM/              # 모델 가중치 (lstm.pt, label.csv)
│
├── model_server/          # Model Server — KoBART + FastText (FastAPI)
│   ├── models/            # 추론 로직 (kobart/, fasttext/)
│   └── assets/            # 모델 가중치 ⚠️ 별도 배치 필요
│       ├── kobart/        # KoBART 체크포인트 (~473MB)
│       └── fasttext/      # FastText 임베딩 cc.ko.300.bin (~6.8GB)
│
├── data_pipeline/         # Airflow DAGs + Spark 스크립트
├── hadoop/                # Hadoop App — HDFS 연동 (FastAPI)
├── ai_models/             # 모델 학습 스크립트
├── postgres/              # DB 초기화 SQL (init.sql — 컨테이너 최초 기동 시 자동 실행)
│
├── nginx.conf             # nginx 리버스 프록시 설정
├── docker-compose.yml
├── .env                   # 환경변수 ⚠️ git 제외 — .env.example 참고
├── .env.example           # 환경변수 템플릿
└── README.md
```

---

## 7. 📊 기대 효과

* 농인의 **SNS 접근성 및 디지털 정보 격차 해소**
* 농인–비농인 간 실시간 양방향 소통 환경 제공
* 수어 기반 AI 기술의 **실제 서비스 적용 사례** 제시

---

## 8. ⚙️ 설치 및 실행 방법 (Docker)

> 모든 서비스는 Docker Compose로 관리됩니다.  
> 아래 단계를 **순서대로** 진행하세요.

---

### STEP 0 — Docker 설치 (Ubuntu 기준, 미설치 시)

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl

sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

#### sudo 없이 Docker 사용하기

```bash
sudo usermod -aG docker $USER
newgrp docker
```

---

### STEP 1 — 저장소 클론 및 프로젝트 디렉토리 이동

```bash
git clone https://github.com/hellojiyeon00/SignTalk.git
cd SignTalk
```

---

### STEP 2 — 환경변수 및 모델 가중치 설정

#### .env 파일 설정

`.env`는 git에 포함되지 않습니다. `.env.example`을 복사해 값을 채워주세요.

```bash
cp .env.example .env
```

반드시 직접 발급해야 하는 API 키:

| 항목 | 발급처 |
|---|---|
| `KAKAO_REST_API_KEY` | [Kakao Developers](https://developers.kakao.com) |
| `DISASTER_SERVICE_KEY` | [재난안전데이터공유플랫폼](https://www.safetydata.go.kr) |
| `LLM_API_KEY` (Gemini) | [Google AI Studio](https://aistudio.google.com) |

> **재난문자 API 주의**: 발급 후 서비스 페이지에서 **서버 IP를 등록**해야 합니다.

#### 모델 가중치 파일 배치

아래 파일들은 용량이 크거나 저작권 이슈로 git에 포함되지 않습니다.  
팀 내부 별도 경로(Google Drive 등)에서 받아 배치하세요.

| 파일 | 크기 | 배치 경로 |
|---|---|---|
| `cc.ko.300.bin` | ~6.8GB | `model_server/assets/fasttext/` |
| KoBART 체크포인트 | ~473MB | `model_server/assets/kobart/final_model_checkpoint-17800/` |

> `model/LSTM/lstm.pt` (31MB)는 git에 포함되어 있어 별도 배치 불필요

---

### STEP 3 — 인프라 서비스 먼저 기동 (PostgreSQL · Redis · Kafka · Hadoop)

```bash
# 인프라 서비스 먼저 실행
docker compose up -d postgres redis kafka hadoop

# 상태 확인 — 모두 healthy 상태가 될 때까지 대기 (약 1~2분)
# hadoop은 NameNode 초기화로 다른 서비스보다 오래 걸릴 수 있습니다
docker compose ps
```

#### 각 서비스 정상 동작 확인

```bash
# PostgreSQL 접속 및 스키마 확인
docker exec -it signtalk-postgres \
  psql -U multicampus_user -d multicampus_db -c "\dt multicampus_schema.*"

# Redis 연결 확인
docker exec -it signtalk-redis \
  redis-cli -a rediscci4 ping
# 정상: PONG

# Kafka 토픽 목록 확인
docker exec -it signtalk-kafka \
  /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# Hadoop WebHDFS 확인
curl -s "http://localhost:9870/webhdfs/v1/?op=LISTSTATUS&user.name=hadoop"
# 정상: {"FileStatuses":...}
```

---

### STEP 4 — DB 스키마 자동 생성

`postgres/init.sql`이 PostgreSQL 컨테이너 최초 기동 시 **자동으로 실행**됩니다.  
별도 DDL 실행 없이 STEP 3 완료 후 모든 테이블과 초기 데이터가 생성됩니다.

```bash
# 테이블 생성 확인
docker exec -it signtalk-postgres \
  psql -U multicampus_user -d multicampus_db -c "\dt multicampus_schema.*"
```

> `docker compose down -v`로 볼륨을 삭제한 뒤 재기동해도 `init.sql`이 자동 재실행됩니다.

---

### STEP 5 — 애플리케이션 서비스 빌드 및 실행

```bash
# 이미지 빌드
docker compose build backend model-app model-server hadoop-app

# 서비스 실행 (Airflow 제외)
docker compose up -d backend model-app model-server hadoop-app nginx

# 전체 상태 확인
docker compose ps
```

---

### STEP 6 — Airflow 실행

```bash
# Airflow 이미지 빌드
docker compose build airflow-webserver

# 초기화 (최초 1회만 — admin 계정 생성)
docker compose up airflow-init

# 웹서버 및 스케줄러 실행
docker compose up -d airflow-webserver airflow-scheduler
```

> Airflow UI: http://localhost:8080

---

### 서비스 포트 정보

| 서비스 | 포트 | 비고 |
|---|---|---|
| Frontend (nginx) | 80 | 메인 진입점 |
| Backend (FastAPI) | 8000 | REST API |
| Model App (LSTM) | 8001 | 수어 인식 모델 |
| Model Server (KoBART + FastText) | 8002 | 텍스트 변환 모델 |
| Hadoop App | 8003 | HDFS 연동 |
| Hadoop NameNode (WebHDFS) | 9870 | HDFS Web UI / WebHDFS API |
| Airflow | 8080 | 파이프라인 관리 |
| PostgreSQL | 5432 | |
| Redis | 6379 | |
| Kafka | 9092 | |

> **+ 포트 변경 방법**
>
> - **브라우저 접속 포트(nginx)만 바꾸는 경우** → `docker-compose.yml` 한 곳만 수정
>   ```yaml
>   # 예: 80 → 9090으로 변경
>   ports:
>     - "9090:80"
>   ```
>   `frontend/js/config.js`의 `API_BASE_URL`이 `""`(빈 문자열)이므로 별도 수정 불필요
>
> - **내부 서비스 포트를 바꾸는 경우** → 아래 파일을 모두 같이 수정해야 함
>   | 서비스 | 수정 파일 |
>   |---|---|
>   | backend | `docker-compose.yml` ports + `nginx.conf` proxy_pass 4곳 |
>   | model-app / model-server | `docker-compose.yml` ports + `.env` MODEL_API_URL / MODEL_SERVER_URL |
>   | hadoop-app | `docker-compose.yml` ports + `.env` HADOOP_API_URL |

---

### 전체 서비스 중지

```bash
# 컨테이너 중지 (데이터 유지)
docker compose down

# 컨테이너 + 볼륨 전체 삭제 (데이터 초기화)
docker compose down -v
```

---

### 전체 서비스 시작

```bash
# 컨테이너 시작
docker compose up -d --build
```

---

### 실시간 로그 확인

```bash
# 전체 서비스 로그 (실시간)
docker compose logs -f

# 특정 서비스 로그만 확인
docker compose logs -f backend
docker compose logs -f model-app
docker compose logs -f model-server
docker compose logs -f nginx
docker compose logs -f hadoop
docker compose logs -f airflow-webserver

# 최근 N줄만 출력 후 실시간 추적
docker compose logs -f --tail=100 backend
```

---


## 9. 📌 향후 계획

- 수어 인식 정확도 향상 (추가 데이터 수집 및 모델 고도화)
- 모바일 환경 지원 (반응형 UI 개선)
- 실시간 영상 통화 기반 수어 통역 기능
- 재난문자 수어 영상 자동 생성 파이프라인 완성
- 사용자 피드백 기반 번역 품질 개선 시스템