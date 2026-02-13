"""
Model Bridge API

Frontend -> Backend -> Model Server 연결용 엔드포인트
(DB / 로그인 의존 없음 - DEV 단계)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.model_client import ModelClient

router = APIRouter()
model_client = ModelClient()


class InferRequest(BaseModel):
    text: str


@router.post("/infer/{task}")
async def infer(task: str, req: InferRequest):
    """
    텍스트를 모델 서버로 전달하고 결과를 반환 (멀티모델)
    """
    try:
        result = await model_client.infer(task, req.text)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Model server error: {e}"
        )

    return result
