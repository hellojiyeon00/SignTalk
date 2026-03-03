"""
models.fasttext

fastText 유사 단어 추천 엔트리
- registry.py에서 fasttext.infer를 호출
- req(dict) 입력 -> 결과(dict) 반환
"""

from __future__ import annotations

from typing import Any, Dict

from .loader import get_model_bundle
from .recommend import recommend


def infer(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    fastText 유사 단어 추천 엔트리

    req는 main.py(InferRequest)에서 model_dump()한 dict:
      {"text": Optional[str], "payload": Optional[dict]}

    허용 입력:
    - payload.tokens: ["KFC", "따뜻", ...]
    - (호환) text: "KFC 따뜻 햄버거"  -> split 해서 tokens 생성
    """
    _ = get_model_bundle()

    payload = req.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    tokens = payload.get("tokens")

    # tokens가 없으면 text로부터 생성(호환)
    if not tokens:
        text = req.get("text") or ""
        tokens = [t for t in str(text).split() if t.strip()]

    print(f"[fasttext.infer] tokens={tokens!r}")

    if not isinstance(tokens, list):
        raise ValueError("tokens must be list[str]")

    top_k = payload.get("top_k", 5)
    threshold = payload.get("threshold", 0.65)
    replace_on = payload.get("replace_on", False)

    return recommend(
        tokens=tokens,
        top_k=int(top_k),
        threshold=float(threshold),
        replace_on=bool(replace_on),
    )
