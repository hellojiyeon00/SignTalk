#!/usr/bin/env bash
# =============================================================
# SignTalk — 최초 환경 설정 및 서비스 기동 스크립트
# 사용법: bash setup.sh
# =============================================================
set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
step()  { echo -e "\n${CYAN}══════════════════════════════════════════════${NC}"; \
          echo -e "${CYAN}  $*${NC}"; \
          echo -e "${CYAN}══════════════════════════════════════════════${NC}"; }

# ── STEP 1. .env 설정 ─────────────────────────────────────────
step "STEP 1 / 6 — 환경변수(.env) 확인"
if [ ! -f .env ]; then
  if [ ! -f .env.example ]; then
    error ".env.example 파일이 없습니다. 저장소가 올바르게 클론되었는지 확인하세요."
  fi
  warn ".env 파일이 없습니다. .env.example을 복사합니다."
  cp .env.example .env
  warn "──────────────────────────────────────────────────────────"
  warn " .env 파일을 열어 아래 항목의 값을 직접 입력한 뒤"
  warn " 다시 이 스크립트를 실행하세요."
  warn ""
  warn "   필수 API 키 목록:"
  warn "   • KAKAO_REST_API_KEY  → https://developers.kakao.com"
  warn "   • DISASTER_SERVICE_KEY → https://www.safetydata.go.kr"
  warn "   • LLM_API_KEY (Gemini) → https://aistudio.google.com"
  warn "──────────────────────────────────────────────────────────"
  exit 1
fi
info ".env 확인 완료"

# ── STEP 2. SSL 인증서 자동 생성 ─────────────────────────────
step "STEP 2 / 6 — SSL 인증서 확인"
if [ ! -f certs/privkey.pem ] || [ ! -f certs/fullchain.pem ]; then
  if ! command -v openssl &>/dev/null; then
    error "openssl이 설치되어 있지 않습니다. 'sudo apt install openssl' 후 다시 실행하세요."
  fi

  HOST_IP=$(hostname -I | awk '{print $1}')
  info "감지된 호스트 IP: ${HOST_IP}"
  mkdir -p certs

  openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout certs/privkey.pem \
    -out certs/fullchain.pem \
    -subj "/C=KR/ST=Seoul/L=Seoul/O=SignTalk/CN=${HOST_IP}" \
    -addext "subjectAltName=IP:${HOST_IP},IP:127.0.0.1,DNS:localhost" \
    2>/dev/null

  info "인증서 생성 완료 → certs/fullchain.pem, certs/privkey.pem"
  info "(유효기간 10년, SAN: IP=${HOST_IP})"
else
  info "기존 SSL 인증서를 사용합니다."
fi

# ── STEP 3. 모델 가중치 존재 여부 안내 ───────────────────────
step "STEP 3 / 6 — 모델 가중치 확인"
MISSING=0
if [ ! -f "model_server/assets/fasttext/cc.ko.300.bin" ]; then
  warn "누락: model_server/assets/fasttext/cc.ko.300.bin (~6.8GB)"
  MISSING=1
fi
if [ ! -d "model_server/assets/kobart/final_model_checkpoint-17800" ]; then
  warn "누락: model_server/assets/kobart/final_model_checkpoint-17800/ (~473MB)"
  MISSING=1
fi
if [ "$MISSING" -eq 1 ]; then
  warn "위 모델 가중치가 없으면 model-server가 정상 동작하지 않습니다."
  warn "팀 내부 공유 경로(Google Drive 등)에서 받아 배치 후 재실행하세요."
  warn "지금은 가중치 없이 계속 진행합니다..."
else
  info "모델 가중치 확인 완료"
fi

# ── STEP 4. 인프라 서비스 기동 및 헬스체크 ───────────────────
step "STEP 4 / 6 — 인프라 서비스 기동 (postgres, redis, kafka, hadoop)"
docker compose up -d postgres redis kafka hadoop

info "서비스가 healthy 상태가 될 때까지 대기 중 (최대 120초)..."
ELAPSED=0
while [ $ELAPSED -lt 120 ]; do
  PG_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' signtalk-postgres 2>/dev/null || echo "none")
  RD_HEALTH=$(docker inspect --format='{{.State.Health.Status}}' signtalk-redis    2>/dev/null || echo "none")
  if [ "$PG_HEALTH" = "healthy" ] && [ "$RD_HEALTH" = "healthy" ]; then
    break
  fi
  sleep 5; ELAPSED=$((ELAPSED + 5))
  info "대기 중... (${ELAPSED}s / PostgreSQL: ${PG_HEALTH}, Redis: ${RD_HEALTH})"
done

if [ "$PG_HEALTH" != "healthy" ] || [ "$RD_HEALTH" != "healthy" ]; then
  warn "인프라 서비스가 아직 준비되지 않을 수 있습니다. 로그를 확인하세요:"
  warn "  docker compose logs postgres redis"
else
  info "인프라 서비스 준비 완료"
fi

# ── STEP 5. 애플리케이션 빌드 및 실행 ───────────────────────
step "STEP 5 / 6 — 애플리케이션 빌드 및 실행"
info "이미지를 빌드합니다 (시간이 걸릴 수 있습니다)..."
docker compose build backend model-app model-server hadoop-app

info "전체 서비스를 실행합니다..."
docker compose up -d backend model-app model-server hadoop-app nginx

# ── STEP 6. Airflow 초기화 및 실행 ──────────────────────────
step "STEP 6 / 6 — Airflow 초기화 및 실행"

# airflow-init은 최초 1회만 실행 (이미 완료된 경우 건너뜀)
INIT_STATUS=$(docker inspect --format='{{.State.Status}}' signtalk-airflow-init 2>/dev/null || echo "none")

if [ "$INIT_STATUS" = "exited" ]; then
  EXIT_CODE=$(docker inspect --format='{{.State.ExitCode}}' signtalk-airflow-init 2>/dev/null || echo "1")
  if [ "$EXIT_CODE" = "0" ]; then
    info "Airflow 초기화가 이미 완료되어 있습니다. 건너뜁니다."
  else
    warn "이전 airflow-init이 실패했습니다. 재실행합니다..."
    docker compose up airflow-init
  fi
else
  info "Airflow DB 마이그레이션 및 admin 계정 생성 중..."
  docker compose up airflow-init
fi

info "Airflow 웹서버 및 스케줄러를 실행합니다..."
docker compose up -d airflow-webserver airflow-scheduler

# ── 완료 메시지 ───────────────────────────────────────────────
HOST_IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       ✅  SignTalk 서비스 기동 완료!                  ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  🌐  https://${HOST_IP}                               "
echo -e "${GREEN}║${NC}  🔀  http://${HOST_IP}  → HTTPS 자동 리다이렉트       "
echo -e "${GREEN}║${NC}                                                       "
echo -e "${GREEN}║${NC}  📊  Airflow UI  :  http://localhost:8080             "
echo -e "${GREEN}║${NC}  🐘  Hadoop UI   :  http://localhost:9870             "
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  ⚠️  브라우저 '인증서 신뢰 불가' 경고 → 정상          "
echo -e "${GREEN}║${NC}      '고급 → 계속 진행(signtalk)'을 클릭하세요        "
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
info "서비스 상태 확인: docker compose ps"
info "로그 확인:        docker compose logs -f backend"
