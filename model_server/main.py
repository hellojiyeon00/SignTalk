"""
main.py

멀티 모델 단일 서버 엔트리
- POST /infer/{task}
- registry를 통해 모델 분기
"""

from __future__ import annotations
from typing import Any, Dict, Optional
import traceback

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from registry import get_handler

from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().with_name(".env")
load_dotenv(dotenv_path=str(ENV_PATH), override=True)


# .env 로드 (export 대신 사용)
load_dotenv()

app = FastAPI(title="Model Server", version="2.0.0")


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