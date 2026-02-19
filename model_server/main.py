"""
main.py

멀티 모델 단일 서버 엔트리
- POST /infer/{task}
- registry를 통해 모델 분기
"""

from __future__ import annotations

from typing import Any, Dict, Optional

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
def infer(task: str, req: InferRequest, request: Request):
    # 호출자 식별 (backend/curl 등)
    caller = request.headers.get("x-caller", "unknown")
    print(f"[INFER] task={task} x-caller={caller}")
    
    handler = get_handler(task)
    if handler is None:
        raise HTTPException(status_code=404, detail=f"unknown task: {task}")

    try:
        result = handler(req.model_dump())
        return {"ok": True, "task": task, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
