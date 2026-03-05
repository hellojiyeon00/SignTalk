#!/usr/bin/env bash
set -euo pipefail

HOST="0.0.0.0"
PORT="8001"
BASE_URL="http://127.0.0.1:${PORT}"

echo "[start] Starting Model Server on ${HOST}:${PORT} ..."

# startup warmup 토글 (main.py의 warmup 로직이 이 값으로 on/off 되는 구조)
export MODEL_WARMUP_FASTTEXT=0

# 서버 백그라운드 실행
uvicorn model_server.main:app --host "${HOST}" --port "${PORT}" &
PID=$!

cleanup() {
  echo "[stop] stopping model server (pid=${PID})"
  kill "${PID}" 2>/dev/null || true
}
trap cleanup EXIT

# 서버 준비 대기 (sleep 대신 포트/엔드포인트 응답으로 확인)
echo "[wait] Waiting for server to be ready..."
for i in {1..60}; do
  if curl -s "${BASE_URL}/docs" >/dev/null 2>&1; then
    echo "[wait] Server is ready."
    break
  fi
  sleep 1
  if [ "${i}" -eq 60 ]; then
    echo "[error] Server not ready in time."
    exit 1
  fi
done

echo "[warmup] Warming up KoBART ..."
curl -s -X POST "${BASE_URL}/infer/kobart" \
  -H "Content-Type: application/json" \
  -d '{"text":"테스트"}' >/dev/null

echo "[warmup] FastText first bundle load (~60s, only on cold start)..."
curl -s -X POST "${BASE_URL}/infer/fasttext" \
  -H "Content-Type: application/json" \
  -d '{"tokens":["테스트"]}' >/dev/null

echo "[done] Warmup done. Model Server running (pid=${PID})."

# foreground로 대기 (스크립트 종료되면 trap으로 서버도 같이 내려감)
wait "${PID}"
