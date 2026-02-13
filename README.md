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
├── backend/ (FastAPI)
│   ├── app/
│   │   ├── api/          # API 엔드포인트
│   │   ├── core/         # 설정 및 보안
│   │   ├── models/       # DB 스키마 (PostgreSQL)
│   │   └── services/     # 핵심 비즈니스 로직 (AI 변환 등)
│   └── main.py
│
├── frontend/ (HTML/JS)
│   ├── assets/           # CSS, Images
│   ├── js/               # Frontend logic
│   ├── chat.html
│   ├── index.html
│   ├── login.html
│   └── signup.html
│
├── data_pipeline/ (Spark / Airflow)
│   ├── dags/             # Airflow DAGs
│   └── scripts/          # Spark processing scripts
│
├── ai_models/ (PyTorch / KoBART)
│   ├── training/         # 학습 스크립트
│   └── weights/          # 모델 가중치 저장소
│
├── requirements.txt
└── README.md
```

---

## 7. 📊 기대 효과

* 농인의 **SNS 접근성 및 디지털 정보 격차 해소**
* 농인–비농인 간 실시간 양방향 소통 환경 제공
* 수어 기반 AI 기술의 **실제 서비스 적용 사례** 제시

---

## 8. ⚙️ 설치 방법

### 1) 저장소 클론

```bash
git clone https://github.com/hellojiyeon00/SignLanguageTalk.git
cd SignLanguageTalk
```

### 2) 가상환경 생성

```bash
conda create -n <env_name>
conda activate <env_name>
```

### 3) 패키지 설치

```bash
pip install -r requirements.txt
```

---

## 9. 📌 향후 계획