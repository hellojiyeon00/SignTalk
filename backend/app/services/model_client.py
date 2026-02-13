"""
모델 클라이언트

Backend -> Model Server HTTP Client
- 멀티 모델 단일 엔드포인트: POST /infer/{task}
- (호환) translate/translate_sync는 내부적으로 kobart infer를 호출
"""

from __future__ import annotations

import os
import time
import logging
import hashlib
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

MODEL_SERVER_BASE_URL = os.getenv("MODEL_SERVER_URL", "http://127.0.0.1:8001")
MODEL_SERVER_TIMEOUT_SEC = float(os.getenv("MODEL_SERVER_TIMEOUT_SEC", "10"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_gloss_from_infer_response(data: Any) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    model_server /infer/{task} 표준 응답에서 gloss/meta를 안전하게 추출한다.

    기대 응답 예:
      {
        "ok": true,
        "task": "kobart",
        "result": {
          "gloss": "...",
          "meta": {...}   # 선택
        }
      }
    """
    if not isinstance(data, dict) or not data.get("ok"):
        raise RuntimeError(f"invalid model_server response: {data}")

    result = data.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("invalid model_server response: missing result")

    gloss = result.get("gloss")
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else None

    if not isinstance(gloss, str) or not gloss.strip():
        raise RuntimeError("invalid model_server response: missing gloss")

    return gloss, meta


class ModelClient:
    def __init__(self, base_url: str = MODEL_SERVER_BASE_URL, timeout_sec: float = MODEL_SERVER_TIMEOUT_SEC):
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    async def infer(self, task: str, text: str) -> Dict[str, Any]:
        """
        멀티 모델 단일 model_server 호출 (비동기)
        - endpoint: POST /infer/{task}
        - response: { ok, task, result, error? }
        """
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")

        url = f"{self.base_url}/infer/{task.strip()}"

        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            response = await client.post(url, json={"text": text})

        response.raise_for_status()
        return response.json()

    def infer_sync(self, task: str, text: str) -> Dict[str, Any]:
        """
        멀티 모델 단일 model_server 호출 (동기)
        """
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")

        url = f"{self.base_url}/infer/{task.strip()}"
        t0 = time.time()

        logger.info(f"[ModelClient] POST {url} timeout={self.timeout_sec}s text_len={len(text)}")
        logger.info(
            "[ModelClient] input_len=%d input_hash=%s preview=%r",
            len(text),
            _sha256(text),
            text[:80],
        )

        with httpx.Client(timeout=self.timeout_sec) as client:
            response = client.post(url, json={"text": text})

        elapsed_ms = int((time.time() - t0) * 1000)
        logger.info(f"[ModelClient] RESP {response.status_code} elapsed_ms={elapsed_ms}")

        response.raise_for_status()
        return response.json()

    async def translate(self, text: str) -> Dict[str, Any]:
        """
        (호환용) 기존 translate 호출을 kobart infer로 연결
        반환 포맷은 기존과 동일하게 {"gloss": ..., "meta": ...} 로 유지
        """
        data = await self.infer("kobart", text)
        gloss, meta = _extract_gloss_from_infer_response(data)
        return {"gloss": gloss, "meta": meta}

    def translate_sync(self, text: str) -> Dict[str, Any]:
        """
        (호환용) 기존 translate_sync 호출을 kobart infer_sync로 연결
        반환 포맷은 기존과 동일하게 {"gloss": ..., "meta": ...} 로 유지
        """
        data = self.infer_sync("kobart", text)
        gloss, meta = _extract_gloss_from_infer_response(data)
        return {"gloss": gloss, "meta": meta}
