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
from .settings import settings
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

    # [v1 호환 입력 정책] KoBART 입력 텍스트 정규화(점 제거 포함)
    # - 예전 /v1/translate 경로에서 model_text로 점(.)이 제거되던 현상과 맞춤
    # - 원인 규명 완료 후, 이 정책을 공용 전처리로 승격(통합)할 예정
    model_text = (
        text.replace("\r\n", "\n").replace("\r", "\n")
            .replace(".", " ")
            .replace("·", " ")
            .strip()
    )

    payload = req.get("payload") or {}

    request_id = payload.get("request_id") or str(uuid.uuid4())
    top_k = int(payload.get("top_k", 1))
    max_new_tokens = int(payload.get("max_new_tokens", settings.max_new_tokens))
    num_beams = int(payload.get("num_beams", settings.num_beams))

    t0 = time.time()

    gloss = generate_gloss(
    bundle=bundle,
    text=model_text,
    top_k=top_k,
    max_new_tokens=max_new_tokens,
    num_beams=num_beams,
    )

    latency_ms = int((time.time() - t0) * 1000)

    return {
    "request_id": request_id,
    "input": text,
    "model_text": model_text,
    "gloss": gloss,
    "meta": {
        "model": bundle.get("model_name", "unknown"),
        "latency_ms": latency_ms,
        "device": bundle.get("device", "cpu"),
        "model_dir": bundle.get("model_dir"),
        "top_k": top_k,
        "max_new_tokens": max_new_tokens,
        "num_beams": num_beams,
    }
}