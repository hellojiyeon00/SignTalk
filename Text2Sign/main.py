"""
main.py

멀티 모델 단일 서버 엔트리
- POST /infer/{task}
- registry를 통해 모델 분기
"""

from __future__ import annotations

import os
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from starlette.concurrency import run_in_threadpool

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# .env 로딩 (반드시 registry import 이전)
# 프로젝트 루트(.env) 명시 로드: uvicorn을 어디서 실행해도 동일하게 동작
REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=False)

print(
    "[ENV CHECK]",
    "KOBART_MODEL_DIR=",
    os.getenv("KOBART_MODEL_DIR"),
    "KOBART_CHECKPOINT=",
    os.getenv("KOBART_CHECKPOINT"),
)

print(
    "[ENV CHECK][FASTTEXT]",
    "FASTTEXT_SIM_BACKEND=",
    os.getenv("FASTTEXT_SIM_BACKEND"),
    "FASTTEXT_PGVECTOR_COL=",
    os.getenv("FASTTEXT_PGVECTOR_COL"),
)

from registry import get_handler
from utils.jsonl_logger import write_jsonl_log

app = FastAPI(title="Model Server", version="2.0.0")

import logging

logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_warmup():
    print("[WARMUP] startup begin")

    # KoBART warmup
    try:
        kobart_handler = get_handler("kobart")
        if kobart_handler is not None:
            await run_in_threadpool(
                kobart_handler,
                {
                    "text": "텍스트",
                    "payload": {
                        "top_k": 1,
                        "max_new_tokens": 8,
                        "num_beams": 1
                    },
                },
            )
            print("[WARMUP] KoBART warmed")
        else:
            print("[WARMUP] KoBART handelr not found")
    except Exception as e:
        print(f"[WARMUP][KoBART] failed: {e}")

    # FastText warmup
    try:
        fasttext_handler = get_handler("fasttext")
        if fasttext_handler is not None:
            await run_in_threadpool(
                fasttext_handler,
                {
                    "text": None,
                    "payload": {
                        "tokens": ["테스트"],
                        "top_k": 10,
                        "threshold": 0.65,
                        "replace_on": False
                    },
                },
            )
            print("[WARMUP] FastText warmed")
        else:
            print("[WARMUP] FastText handler not found")
    except Exception as e:
        print(f"[WARMUP][FastText] failed: {e}")

    print("[WARMUP] startup end")

class InferRequest(BaseModel):
    """
    공통 요청 스키마
    """

    text: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/infer/{task}")
async def infer(task: str, req: InferRequest):
    t0 = time.time()

    handler = get_handler(task)
    if handler is None:
        raise HTTPException(status_code=404, detail=f"unknown task: {task}")

    # fasttext 요청이면 tokens 길이도 함께 로깅
    tokens_len = -1
    try:
        payload = req.payload or {}
        toks = payload.get("tokens") if isinstance(payload, dict) else None
        if isinstance(toks, list):
            tokens_len = len(toks)
    except Exception:
        tokens_len = -1

    logger.info("[infer] start task=%s tokens_len=%s", task, tokens_len)

    # 입력 길이 (확실히 알 수 있는 값만)
    text_len = -1
    try:
        if isinstance(req.text, str):
            text_len = len(req.text)
    except Exception:
        text_len = -1

    try:
        handler_t0 = time.time()
        result = await run_in_threadpool(handler, req.model_dump())
        handler_elapsed_ms = int((time.time() - handler_t0) * 1000)

        if result is None:
            raise RuntimeError(f"handler for task '{task}' returned None")

        elapsed_ms = int((time.time() - t0) * 1000)

        logger.info("[infer] done task=%s elapsed_ms=%d", task, elapsed_ms)

        # 성공 로그 (로깅 실패해도 inference는 그대로 진행)
        try:
            # result 구조는 handler마다 다를 수 있으므로 "안전 추출"만 한다.
            request_id = result.get("request_id") if isinstance(result, dict) else None
            input_text = result.get("input") if isinstance(result, dict) else None
            gloss = result.get("gloss") if isinstance(result, dict) else None

            meta = result.get("meta") if isinstance(result, dict) else None
            if not isinstance(meta, dict):
                meta = {}

            write_jsonl_log(
                {
                    "ok": True,
                    "task": task,
                    "elapsed_ms": elapsed_ms,
                    "handler_elapsed_ms": handler_elapsed_ms,
                    "model_latency_ms": meta.get("latency_ms"),
                    "tokens_len": tokens_len,
                    "text_len": text_len,
                    "request_id": request_id,
                    "input": input_text,
                    "gloss": gloss,
                    "device": meta.get("device"),
                    "model_dir": meta.get("model_dir"),
                    "result": result,
                }
            )
        except Exception:
            logger.exception("[infer][jsonl] write failed (success)")

        return {"ok": True, "task": task, "result": result}

    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)

        logger.exception(
            "[infer] fail task=%s elapsed_ms=%d",
            task,
            elapsed_ms
        )

        # 실패 로그
        try:
            write_jsonl_log(
                {
                    "ok": False,
                    "task": task,
                    "elapsed_ms": elapsed_ms,
                    "tokens_len": tokens_len,
                    "text_len": text_len,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
        except Exception:
            logger.exception("[infer][jsonl] write failed (fail)")

        raise HTTPException(status_code=500, detail=str(e))