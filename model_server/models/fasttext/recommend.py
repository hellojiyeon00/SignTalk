"""
recommend.py

역할
- 입력 토큰에 대해 fastText 벡터 기반 유사도 검색 수행
"""

from __future__ import annotations
from typing import Any, Dict, List
from .loader import get_model_bundle
import json
import os
import ast
import math

# List[tuple[word, url, vector]]
_CORPUS_CACHE = None

def parse_vector(raw: Any) -> List[float]:
    """
    corpus.vector 파싱 유틸
    
    지원 포맷
    - list: [0.1, -0.2, ...] (이미 파싱된 경우)
    - str(JSON): "[0.1, -0.2, ...]"
    - str(Python literal): "[0.1, -0.2, ...]" (json 파싱 실패 시)

    반환
    - List[float]
    """
    if raw in None:
        raise ValueError("vector is None")
    
    # 이미 list면 그대로 float 변환
    if isinstance(raw, list):
        return [float(x) for x in raw]
    
    # 문자열이면 json -> ast 순서로 파싱
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            raise ValueError("empty vector string")
        
        try:
            arr = json.loads(s)
        except Exception:
            arr = ast.literal_eval(s)

        if not isinstance(arr, list):
            raise ValueError(f"parsed vector is not list: type={type(arr)}")
        
        return [float(x) for x in arr]
    
    raise ValueError(f"unsupported vector type: {type(raw)}")


def _cosine(a: List[float], b: List[float]) -> float:
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _embed(ft_model: Any, token: str) -> List[float]:
    # fasttext python binding 기준
    return list(ft_model.get_word_vector(token))


def _load_corpus_cache():
    global _CORPUS_CACHE
    if _CORPUS_CACHE is not None:
        return _CORPUS_CACHE

    path = os.getenv("CORPUS_VECTORS_PATH", "corpus_vectors.json")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    items = []
    for row in raw:
        w = row.get("word_name")
        url = row.get("url_path")
        vec_raw = row.get("vector")

        if not (isinstance(w, str) and isinstance(url, str)):
            continue

        try:
            vec = parse_vector(vec_raw)
        except Exception:
            # 벡터 포맷이 깨진 row는 스킵 (로그 필요하면 logger 붙이기)
            continue

        items.append((w, url, vec))

    _CORPUS_CACHE = items
    return _CORPUS_CACHE


def recommend(tokens: List[str], top_k: int = 5, threshold: float = 0.65):

    bundle = get_model_bundle()

    safe_tokens = [str(t) for t in tokens if isinstance(t, (str, int, float)) and str(t).strip()]

    ft_model = (
        bundle.get("model")
        or bundle.get("ft")
        or bundle.get("fasttext")
        or bundle.get("ft_model")
    )
    if ft_model is None:
        raise RuntimeError(f"get_model_bundle()에서 fastText 모델을 찾지 못했습니다. keys={list(bundle.keys())}")

    corpus_items = _load_corpus_cache()

    results: Dict[str, Dict[str, Any]] = {}
    for t in safe_tokens:
        tv = _embed(ft_model, t)

        best_word = None
        best_url = None
        best_score = 0.0

        for w, url, vec in corpus_items:
            s = _cosine(tv, vec)
            if s > best_score:
                best_score = s
                best_word = w
                best_url = url

        if best_score >= threshold and best_word is not None:
            results[t] = {"best": best_word, "score": float(round(best_score, 4)), "url": best_url}
        else:
            results[t] = {"best": None, "score": float(round(best_score, 4)), "url": None}

    return {
        "results": results,
        "meta": {
            "note": "fasttext step3 (cosine top1)",
            "top_k": top_k,
            "threshold": threshold,
            "corpus_size": len(corpus_items),
        },
    }



