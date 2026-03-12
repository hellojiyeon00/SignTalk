#!/usr/bin/env bash
set -euo pipefail

HOST="0.0.0.0"
PORT="8002"
BASE_URL="http://127.0.0.1:${PORT}"

echo "[start] Starting Model Server on ${HOST}:${PORT} ..."

uvicorn model_server.main:app --host "${HOST}" --port "${PORT}" --workers 1 &
PID=$!

cleanup() {
  echo "[stop] stopping model server (pid=${PID})"
  kill "${PID}" 2>/dev/null || true
}
trap cleanup EXIT

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

# KoBART warmup (default ON)
if [ "${WARMUP_KOBART:-1}" = "1" ]; then
  echo "[warmup] Warming up KoBART ..."
  curl -s -X POST "${BASE_URL}/infer/kobart" \
    -H "Content-Type: application/json" \
    -d '{"text":"테스트","payload":{"top_k":1,"max_new_tokens":8,"num_beams":1}}' >/dev/null
else
  echo "[warmup] KoBART warmup skipped"
fi

# FastText warmup (default ON)
if [ "${WARMUP_FASTTEXT:-1}" = "1" ]; then
  echo "[warmup] FastText first bundle load (~60s)..."
  curl -s -X POST "${BASE_URL}/infer/fasttext" \
    -H "Content-Type: application/json" \
    -d '{"payload":{"tokens":["테스트"],"top_k":10,"threshold":0.65,"replace_on":false}}' >/dev/null
else
  echo "[warmup] FastText warmup skipped"
fi

echo "[done] Warmup done. Model Server running (pid=${PID})."

wait "${PID}"
