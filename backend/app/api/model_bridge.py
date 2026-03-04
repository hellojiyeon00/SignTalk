"""Model Bridge API — Frontend → Backend → Model Server 프록시"""

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Optional

from app.services.model_client import ModelClient

router = APIRouter()
model_client = ModelClient()


class InferRequest(BaseModel):
    text: Optional[str] = None
    payload: Optional[dict] = None


@router.post("/infer/{task}")
async def infer(task: str, req: InferRequest):
    """텍스트 또는 payload를 모델 서버로 전달하고 결과를 반환"""
    try:
        if req.payload is not None:
            result = await run_in_threadpool(
                model_client.infer_payload_sync, task, req.payload
            )
        elif req.text:
            result = await run_in_threadpool(
                model_client.infer_sync, task, req.text
            )
        else:
            raise ValueError("text 또는 payload 중 하나는 필수입니다.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model server error: {e}")

    return result
