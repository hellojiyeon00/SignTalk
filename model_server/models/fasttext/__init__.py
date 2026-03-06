"""
models.fasttext

fastText 유사 단어 추천 엔트리
- registry.py에서 fasttext.infer를 호출
- req(dict) 입력 -> 결과(dict) 반환
"""

from __future__ import annotations

import time
import logging
from typing import Any, Dict

from .loader import get_model_bundle
from .recommend import recommend

logger = logging.getLogger(__name__)


def infer(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    fastText 유사 단어 추천 엔트리

    req는 main.py(InferRequest)에서 model_dump()한 dict:
      {"text": Optional[str], "payload": Optional[dict]}

    허용 입력:
    - payload.tokens: ["KFC", "따뜻", ...]
    - (호환) text: "KFC 따뜻 햄버거"  -> split 해서 tokens 생성
    """
    t0 = time.time()

    # bundle 로딩/획득
    t_a0 = time.time()
    _ = get_model_bundle()
    bundle_ms = int((time.time() - t_a0) * 1000)

    payload = req.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    # tokens 준비
    t_b0 = time.time()
    tokens = payload.get("tokens")

    # tokens가 없으면 text로부터 생성(호환)
    if not tokens:
        text = req.get("text") or ""
        tokens = [t for t in str(text).split() if t.strip()]
    prep_ms = int((time.time() - t_b0) * 1000)

    logger.info("[fasttext.infer] tokens=%r", tokens)

    if not isinstance(tokens, list):
        raise ValueError("tokens must be list[str]")

    top_k = payload.get("top_k", 5)
    threshold = payload.get("threshold", 0.65)
    replace_on = payload.get("replace_on", False)

    # recommend 실행
    t_c0 = time.time()
    out = recommend(
        tokens=tokens,
        top_k=int(top_k),
        threshold=float(threshold),
        replace_on=bool(replace_on),
        )
    recommend_ms = int((time.time() - t_c0) * 1000)

    total_ms = int((time.time() - t0) * 1000)
    logger.warning(
        "[fasttext.infer][timing] bundle_ms=%d prep_ms=%d recommend_ms=%d total_ms=%d",
        bundle_ms, prep_ms, recommend_ms, total_ms
    )
    return out
