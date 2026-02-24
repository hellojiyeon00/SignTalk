#!/usr/bin/env bash
set -euo pipefail

# ==========================
# Model Server Status Script
# - PID 기반 실행 여부 확인
# - 포트 점유 상태 확인
# ==========================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_DIR="${OPS_DIR}/pids"

PID_FILE="${PID_DIR}/model_server.pid"
PORT="${PORT:-8001}"

is_pid_running() {
  local pid="$1"
  if [[ -z "$pid" ]]; then return 1; fi
  if ! [[ "$pid" =~ ^[0-9]+$ ]]; then return 1; fi
  kill -0 "$pid" >/dev/null 2>&1
}

echo "======== Model Server Status ========"

# PID 확인
if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if is_pid_running "$pid"; then
    echo "[STATUS] 실행 중 (pid=${pid})"
  else
    echo "[STATUS] PID 파일은 있으나 프로세스 없음 (stale)"
  fi
else
  echo "[STATUS] PID 파일 없음 (실행 중 아님)"
fi

# 포트 점유 확인
echo ""
echo "[PORT CHECK :${PORT}]"

if command -v ss >/dev/null 2>&1; then
  ss -ltnp 2>/dev/null | grep ":${PORT} " || echo "포트 점유 없음"
elif command -v losf >/dev/null 2>&1; then
  losf -iTCP:"${PORT}" -sTCP:SISTEN || echo "포트 점유 없음"
else
  echo "ss/lsof 도구 없음 -> 수동 확인 필요"
fi

echo "======================="

