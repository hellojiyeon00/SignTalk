# 🏭 model_server (Production Guide)

> 부트캠프 프로젝트 운영용  
> 멀티 모델 단일 FastAPI 서버

---

# 🌐 운영 환경

| 항목 | 내용 |
|------|------|
| Infra | AWS EC2 (Ubuntu) |
| GPU | 1개 (g4dn / g5 등) |
| Server | Single FastAPI Instance |
| Worker | uvicorn 1 worker 권장 |

### 지원 모델

- **KoBART** (GPU)
- **LSTM** (CPU 또는 선택적 GPU)
- **FastText** (CPU)
- **LLM** (로컬 GPU 또는 외부 API)

---

# 🧠 설계 원칙 (Production 기준)

## 1️⃣ 단일 프로세스 운영

- `uvicorn --workers 1` 권장
- GPU 모델은 단일 프로세스에서 관리

## 2️⃣ Lazy Loading 전략

- 서버 시작 시 모든 모델 preload ❌
- 최초 요청 시 `load()`
- 이후 전역 캐시 유지

## 3️⃣ GPU 메모리 보호 전략

- KoBART → GPU 우선
- FastText → CPU 고정
- LSTM → 기본 CPU
- LLM → 가능하면 외부 API 권장
- 로컬 LLM 사용 시 GPU 메모리 사용량 반드시 확인

---

# 📁 폴더 구조

```
model_server/

  main.py
    - FastAPI 엔트리
    - POST /infer/{task}

  registry.py
    - task → handler 매핑

  models/
    kobart.py
    lstm.py
    fasttext.py
    llm.py

  assets/
    kobart/
    lstm/
    fasttext/
    llm/

  requirements.txt
  README.md
```

---

# 🚀 실행 방법 (운영 모드)

## 1️⃣ 가상환경 활성화

```bash
source venv/bin/activate
```

## 2️⃣ 의존성 설치

```bash
pip install -r requirements.txt
```

## 3️⃣ GPU 확인

```bash
nvidia-smi
```

## 4️⃣ 서버 실행 (Production)

```bash
uvicorn main:app \
    --host 0.0.0.0 \
    --port 8001 \
    --workers 1
```

> ⚠ `--reload` 사용 금지 (운영 환경)

---

# ⚙️ 환경 변수 권장 설정

```
MODEL_BASE_PATH=/home/ubuntu/model_server/assets
DEVICE=cuda
LOG_LEVEL=info
```

### 예시 실행

```bash
DEVICE=cuda uvicorn main:app --host 0.0.0.0 --port 8001
```

---

# 🎮 GPU 운영 전략

## 기본 원칙

1. 서버 시작 시 모델을 모두 GPU에 올리지 말 것
2. `load()` 내부에서 조건 처리

```python
if DEVICE == "cuda":
    model.to("cuda")
```

3. 사용하지 않는 모델은 GPU에 올리지 않기

## CUDA OOM 발생 시 대응

- LLM 분리 운영 고려
- LSTM을 CPU로 고정
- batch size 감소

---

# 📈 성능 고려 사항

| 모델 | 권장 장치 | 특성 |
|------|-----------|------|
| KoBART | GPU | 추론 비용 높음 |
| FastText | CPU | ms 단위 응답 |
| LSTM | CPU | 중간 수준 |
| LLM | GPU 또는 외부 | 가장 무거움 |

### 동시 요청 증가 시

- 단일 worker 구조 → 직렬 처리
- 추후 확장:
  - `gunicorn + uvicorn workers`
  - LLM 분리 서버화

---

# 🚨 장애 대응 체크리스트

## 1️⃣ 서버 다운

- `journalctl -u 서비스명`
- uvicorn 로그 확인

## 2️⃣ GPU 오류

```bash
nvidia-smi
```

- CUDA OOM 여부 확인

## 3️⃣ 모델 경로 오류

- `assets/` 경로 확인
- checkpoint 존재 여부 확인

---

# 🔐 보안 권장 사항

- EC2 보안 그룹에서 8001 포트 제한
- 내부 통신 전용이면 `0.0.0.0` 대신 내부 IP 바인딩 고려
- LLM 외부 API Key는 `.env`로 관리

---

# 🏁 운영 결론

단일 GPU EC2 환경에서는:

- KoBART 중심 구조로 운영
- FastText는 CPU
- LLM은 외부 API 권장
- 모델 로딩은 Lazy Loading
- uvicorn worker 1개 유지

---

### 📌 Summary

이 구조는 **단일 GPU 환경에서 안정성, 확장성, 메모리 보호 전략을 고려한 운영 설계**이다.
