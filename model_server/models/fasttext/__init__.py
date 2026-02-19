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
    req 예:
    {
    "payload": {
        "tokens": ["KFC", "따뜻", "햄버거"],
        "top_k": 5,
        "threshold": 0.65
        }
    }
    """
    # 로딩만 확인 (캐시)
    _ = get_model_bundle()

    payload = req.get("payload") or {}
    tokens = payload.get("tokens") or []
    if not isinstance(tokens, list):
        raise ValueError("payload.tokens must be list[str]")
    
    top_k = payload.get("top_k", 5)
    threshold = payload.get("threshold", 0.65)

    result = recommend(tokens=tokens, top_k=int(top_k), threshold=float(threshold))
    return result

