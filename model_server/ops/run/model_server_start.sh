#!/usr/bin/env bash
set -euo pipefail

# =======================================
# Model Server Start Script (nohup + PID)
# - AWS bash 환경에서 안정 실행용
# - 포트 점유/잔존 프로세스 방지
# ========================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_DIR="${OPS_DIR}/pids"
LOG_DIR="${OPS_DIR}/logs"

PID_FILE="${PID_DIR}/model_server.pid"
LOG_FILE="${LOG_DIR}/model_server.out"

APP_MODULE="${APP_MODULE:-main:app}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8001}"
WORKERS="${WORKERS:-1}"

usage() {
  cat <<EOF
사용법:
  ./ops/run/model_server_start.sh [-p PORT] [-h HOST] [-w WORKERS]

옵션:
  -p 포트 (기본: 8001)
  -h 호스트 (기본: 0.0.0.0)
  -w 워커 수 (기본: 1)

환경변수(선택):
  APP_MODULE=main:app
  HOST=0.0.0.0
  PORT=8001
  WORKERS=1
EOF
}

while getopts ":p:h:w:" opt; do
  case "$opt" in
    p) PORT="$OPTARG" ;;
    h) HOST="$OPTARG" ;;
    w) WORKERS="$OPTARG" ;;
    *) usage; exit 1 ;;
  esac
done

mkdir -p "$PID_DIR" "$LOG_DIR"

is_pid_running() {
  local pid="$1"
  if [[ -z "$pid"  ]]; then return 1; fi
  if ! [[  "$pid" =~ ^[0-9]+$ ]]; then return 1; fi
  kill -0 "$pid" >/dev/null 2>&1
}

if [[  -f "$PID_FILE"  ]]; then
  old_pid="$(cat "$PID_FILE" || true)"
  if is_pid_running "$old_pid"; then
    echo "[START] 이미 실행 중입니다. pid=${old_pid}"
    echo "        중지: ./ops/run/model_server_stop.sh"
    exit 0
  else
    echo "[START] stale PID 파일 감지 -> 제거 (pid_file=${PID_FILE}, value=${old_pid}"
    rm -f "$PID_FILE"
  fi
fi

# 포트 점유 검사 (ss 우선, 없으면 lsof 시도)
if command -v ss >/dev/null 2>&1; then
  if ss -ltnp 2>/dev/null | grep -q ":${PORT} "; then
    echo "[START][ERROR] 포트 ${PORT} 가 이미 점유 중입니다."
    echo "  확인: ss -ltnp | grep :${PORT}"
    exit 1
  fi
elif command -v lsof >/dev/null 2>&1; then
  if lsof -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "[START][ERROR] 포트 ${PORT} 가 이미 점유 중입니다."
    echo "  확인: lsof -iTCP:${PORT} -sTCP:LISTEN"
    exit 1
  fi
else
  echo "[START][WARN] 포트 점유 검사용(ss/lsof) 도구가 없습니다. 포트 충돌은 수동 확인 필요."
fi

echo "[START] uvicorn ${APP_MODULE} --host ${HOST} --port ${PORT} --workers ${WORKERS}"
echo "[START] log=${LOG_FILE}"
echo "[START] pid_file=${PID_FILE}"

nohup uvicorn "${APP_MODULE}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  > "${LOG_FILE}" 2>&1 &

new_pid="$!"
echo "${new_pid}" > "${PID_FILE}"

sleep 0.3
if is_pid_running "${new_pid}"; then
  echo "[START] OK pid=${new_pid}"
else
  echo "[START][ERROR] 프로세스가 바로 종료되었습니다. 로그를 확인하세요: ${LOG_FILE}"
  exit 1
fi

