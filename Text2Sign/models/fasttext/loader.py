"""
loader.py

역할
- fastText 모델을 1회 로딩하고 캐시한다.
- 서버 재요청마다 재로딩하지 않도록 singleton 패턴 사용.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

# pip install fasttext
import fasttext

_MODEL_BUNDLE: Dict[str, Any] | None = None
_CORPUS_WARMED: bool = False


def get_model_bundle() -> Dict[str, Any]:
    global _MODEL_BUNDLE

    if _MODEL_BUNDLE is not None:
        return _MODEL_BUNDLE
    
    model_path = os.getenv("FASTTEXT_MODEL_PATH")
    if not model_path:
        raise RuntimeError("FASTTEXT_MODEL_PATH is not set")
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"fastText model not found: {model_path}")
    
    model = fasttext.load_model(model_path)

    _MODEL_BUNDLE = {
        "model": model,
        "model_name": "fasttext"
    }

    return _MODEL_BUNDLE


def embed_token(token: str) -> Optional[List[float]]:
    """
    단일 토큰을 fastText 임베딩 벡터로 변환한다.
    corpus에 존재하지 않아도 벡터는 생성되어야 한다.
    """
    if token is None:
        return None
    
    t = token.strip()
    if not t:
        return None
    
    bundle = get_model_bundle()
    model = bundle.get("model") if isinstance(bundle, dict) else None
    if model is None:
        return None
    
    try:
        vec = model.get_word_vector(t)
        return vec.tolist() if hasattr(vec, "tolist") else list(vec)
    except Exception:
        return None
    

def warmup_corpus_cache() -> None:
    """
    corpus 캐시 warm-up (1회)

    - cold start에서 발생하던 corpus 전량 로딩/벡터 파싱 비용을
      서버 부팅 시점으로 이동시켜 timeout을 제거한다.
    - 여러 번 호출돼도 1회만 실행되도록 idempotent 하게 동작한다.
    """
    global _CORPUS_WARMED
    if _CORPUS_WARMED:
        return

    try:
        # fastText 모델 선로딩 (요청 경로에서 load_model이 돌지 않게)
        get_model_bundle()
        print("[WARMUP] fasttext model loaded")

        # corpus 캐시 warm-up (기존)
        from Text2Sign.models.fasttext.recommend import _load_corpus_cache
        _load_corpus_cache()
        print("[WARMUP] fasttext corpus cache warmed")
        
        _CORPUS_WARMED = True
    except Exception:
        # 서버 기동을 막지 않도록 예외는 삼키되, 로그는 상위(main.py)에서 남긴다.
        return

