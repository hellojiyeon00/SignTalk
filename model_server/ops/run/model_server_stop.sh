#!/user/bin/env bash
set -euo pipefail

# ========================================
# Model Server Stop Script (PID 기반 종료)
# ========================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_DIR="${OPS_DIR}/pids"

PID_FILE="${PID_DIR}/model_server.pid"

is_pid_running() {
  local pid="$1"
  if [[ -z "$pid" ]]; then return 1; fi
  if ! [[ "$pid" =~ ^[0-9]+$ ]]; then return 1; fi
  kill -0 "$pid" >/dev/null 2>&1
}

if [[ ! -f "$PID_FILE" ]]; then
  echo "[STOP] PID 파일이 없습니다. 이미 종료된 상태일 수 있습니다."
  exit 0
fi

pid="$(cat "$PID_FILE" || true)"

if ! is_pid_running "$pid"; then
  echo "[STOP] 실행 중이 아닙니다. stale PID 파일 제거."
  rm -f "$PID_FILE"
  exit 0
fi

echo "[STOP] pid=${pid} 종료 시도..."

kill "$pid"

# 최대 5초 대기
for i in {1..5}; do
  if is_pid_running "$pid"; then
    sleep 1
  else
    break
  fi
done

if id_pid_running "$pid"; then
  echo "[STOP] 정상 종료 실패 -> 강제 종료(SIGKILL)"
  kill -9 "$pid"
fi

rm -f "$PID_FILE"

echo "[STOP] 완료."

