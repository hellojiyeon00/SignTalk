"""
loader.py

역할
- fastText 모델을 1회 로딩하고 캐시한다.
- 서버 재요청마다 재로딩하지 않도록 singleton 패턴 사용.
"""

from __future__ import annotations

import os
from typing import Any, Dict

# pip install fasttext
import fasttext

_MODEL_BUNDLE: Dict[str, Any] | None = None


def get_model_bundle() -> Dict[str, Any]:
    global _MODEL_BUNDLE

    if _MODEL_BUNDLE is not None:
        return _MODEL_BUNDLE
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    model_path = os.path.join(base_dir, "assets", "fasttext", "cc.ko.300.bin")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"fastText model not found: {model_path}")
    
    model = fasttext.load_model(model_path)

    _MODEL_BUNDLE = {
        "model": model,
        "model_name": "fasttext"
    }

    return _MODEL_BUNDLE
