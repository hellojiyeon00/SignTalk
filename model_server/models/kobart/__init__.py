"""
models.kobart

KoBART 모델 엔트리
- registry.py에서 kobart.infer를 호출
- req(dict) 입력 → 결과(dict) 반환
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from .loader import get_model_bundle
from .generate import generate_gloss


def infer(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    req 예:
    {
        "text": "...",
        "payload": {
            "request_id": "...",
            "top_k": 1,
            "max_new_tokens": 64,
            "num_beams": 4
        }
    }
    """

    bundle = get_model_bundle()

    text = (req.get("text") or "").strip()
    if not text:
        raise ValueError("text is required")

    payload = req.get("payload") or {}

    request_id = payload.get("request_id") or str(uuid.uuid4())
    top_k = int(payload.get("top_k", 1))
    max_new_tokens = int(payload.get("max_new_tokens", 64))
    num_beams = int(payload.get("num_beams", 4))

    t0 = time.time()

    gloss = generate_gloss(
        bundle=bundle,
        text=text,
        top_k=top_k,
        max_new_tokens=max_new_tokens,
        num_beams=num_beams,
    )

    latency_ms = int((time.time() - t0) * 1000)

    return {
        "request_id": request_id,
        "input": text,
        "gloss": gloss,
        "meta": {
            "model": bundle.get("model_name", "unknown"),
            "latency_ms": latency_ms,
            "device": bundle.get("device", "cpu"),
        },
    }
