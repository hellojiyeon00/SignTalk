"""
main.py

멀티 모델 단일 서버 엔트리
- POST /infer/{task}
- registry를 통해 모델 분기
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

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

from model_server.registry import get_handler  # noqa: E402

app = FastAPI(title="Model Server", version="2.0.0")

import logging  # noqa: E402

logger = logging.getLogger(__name__)


@app.on_event("startup")
def warmup_fasttext() -> None:
    """
    서버 부팅 시 fastText corpus 캐시 warm-up

    - 첫 요청에서 발생하던 corpus 전량 로딩/벡터 파싱 비용을
      부팅 시점으로 이동시켜 timeout을 제거한다.
    """
    try:
        from model_server.models.fasttext.loader import warmup_corpus_cache

        warmup_corpus_cache()
        logger.info("[startup][fasttext] corpus cache warm-up done")
    except Exception:
        logger.exception("[startup][fasttext] corpus cache warm-up failed")


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
def infer(task: str, req: InferRequest):
    handler = get_handler(task)
    if handler is None:
        raise HTTPException(status_code=404, detail=f"unknown task: {task}")

    try:
        result = handler(req.model_dump())

        if result is None:
            raise RuntimeError(f"handler for task '{task}' returned None")

        return {"ok": True, "task": task, "result": result}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    