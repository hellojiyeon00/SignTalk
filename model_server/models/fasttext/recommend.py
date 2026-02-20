"""
recommend.py

fastText 벡터 기반 유사도 추천
- corpus 테이블에서 (word_name, url_path, vector)를 서버 시작 시 1회 캐시
- 요청 시 캐시에서 cosine 유사도도로 top-k 추천
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, List, Tuple, Any

from sqlalchemy import create_engine, text


logger = logging.getLogger(__name__)

# 전역 캐시
# token -> (url_path, vector_list, norm)
_CORPUS_CACHE: Dict[str, Tuple[str, List[float], float]] = {}
_CACHE_LOADED: bool = False
_CACHE_LOADED_AT: float | None = None


def _get_database_url() -> str:
    """
    DB 접속 URL을 환경변수에서 가져온다.

    우선순위:
    1) MODEL_SERVER_DATABASE_URL
    2) DATABASE_URL
    """
    url = os.getenv("MODEL_SERVER_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DB 접속 URL이 없습니다."
            "MODEL_SERVER_DATABASE_URL 또는 DATABASE_URL 환경변수를 설정하세요."
        )
    return url


def parse_vector(raw: Any) -> List[float]:
    """
    DB에 저장된 vector 문자열을 float 리스트로 변환한다.

    허용 예:
    - "[0.1, 0.2, 0.3]"
    - "0.1,0.2,0.3"
    - "0.1 0.2 0.3"
    """
    if raw is None:
        return []
    
    s = raw.strip()
    if not s:
        return []
    
    # 대괄호 제거
    if s[0] == "[' and s[-1] == ']":
        s = s[1:-1].strip()

    # 구분자 통일(콤마/공백 혼용 대응)
    s = s.replace(",", " ")
    parts = [p for p in s.split() if p]

    out: List[float] = []
    for p in parts:
        try:
            out.append(float(p))
        except ValueError:
            # 벡터에 이상치가 섞인 경우 방어
            continue
    return out
   

def _l2_norm(vec: List[float]) -> float:
    """
    L2 norm 계산 (cosine 유사도용)
    """
    acc = 0.0
    for x in vec:
        acc += x * x
    return acc ** 0.5


def _embed(ft_model: Any, token: str) -> List[float]:
    # fasttext python binding 기준
    return list(ft_model.get_word_vector(token))


# DB 로딩 전용으로 변경함
def _load_corpus_cache() -> None:
    """
    corpus 테이블에서 word_name, url_path, vector를 읽어 전역 캐시에 적재한다.
    서버 시작 시 1회 호출을 권장한다.
    """
    global _CORPUS_CACHE, _CACHE_LOADED, _CACHE_LOADED_AT

    t0 = time.time()
    db_url = _get_database_url()

    engine = create_engine(db_url, pool_pre_ping=True)

    sql = text(
        """
        SELECT word_name, url_path, vector
        FROM multicampus_schema.corpus
        WHERE word_name IS NOT NULL
            AND url_path IS NOT NULL
            AND vector IS NOT NULL 
        """
    )
    loaded = 0
    skipped = 0
    cache: Dict[str, Tuple[str, List[float], float]] = {}

    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()

    for word_name, url_path, raw_vector in rows:
        token = str(word_name).strip()
        if not token:
            skipped += 1
            continue

        vec = parse_vector(str(raw_vector))
        if not vec:
            skipped += 1
            continue

        norm = _l2_norm(vec)
        if norm == 0.0:
            skipped += 1
            continue

        cache[token] = (str(url_path), vec, norm)
        loaded += 1

    _CORPUS_CACHE = cache
    _CACHE_LOADED = True
    _CACHE_LOADED_AT = time.time()

    logger.info(
        "[fasttext][cache] loaded=%d skipped=%d elapsed_ms=%d",
        loaded,
        skipped,
        int((time.time() - t0) * 1000)
    )


def initialize_cache(force: bool = False) -> None:
    """
    앱 시작 시 호출하는 캐시 초기화 함수.
    """
    if _CACHE_LOADED and not force:
        return
    _load_corpus_cache()


def recommend_by_similarity(token: str, top_k: int = 5) -> List[Tuple[str, float, str]]:
    """
    token과 가장 유사한 단어 top-k 추천

    반환: [(추천단어, 유사도, url_path), ...]
    """
    if not _CACHE_LOADED:
        _load_corpus_cache()

    q = token.strip()
    if not q:
        return []
    
    # 쿼리 토큰이 corpus에 존재하면 "자기 자신" 제외 추천이 자연스러움
    q_item = _CORPUS_CACHE.get(q)
    if not q_item:
        return []
    
    _, q_vec, q_norm = q_item

    scored: List[Tuple[str, float, str]] = []
    for w, (url, vec, norm) in _CORPUS_CACHE.items():
        if w == q:
            continue

        # cosine = dot(a, b) / (||a|| * ||b||)
        dot = 0.0
        # 길이 불일치 방어: 더 짧은 쪽 기준
        n = min(len(q_vec), len(vec))
        for i in range(n):
            dot += q_vec[i] * vec[i]

        sim = dot / (q_norm * norm)
        scored.append((w, sim, url))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[: max(1, top_k)]   


def recommend(tokens: List[str], top_k: int = 5, threshold: float = 0.65):
    initialize_cache()

    safe_tokens = [
        str(t).strip()
        for t in tokens
        if isinstance(t, (str, int, float)) and str(t).strip()
    ]

    results: Dict[str, Dict[str, Any]] = {}

    for t in safe_tokens:
        candidates = recommend_by_similarity(t, top_k=top_k)

        if not candidates:
            results[t] = {
                "best": None,
                "score": 0.0,
                "url": None,
                "candidates": [],
                "reason": "token_not_in_corpus_or_empty",
            }
            continue

        cand_list = [
            {"word": w, "score": float(round(s, 4)), "url": url}
            for (w, s, url) in candidates
        ]

        best = cand_list[0]
        if best["score"] >= threshold:
            results[t] = {
                "best": best["word"],
                "score": best["score"],
                "url": best["url"],
                "candidates": cand_list,
            }
        else:
            results[t] = {
                "best": None,
                "score": best["score"],
                "url": None,
                "candidates": cand_list,
            }

    return {
        "results": results,
        "meta": {
            "note": "fasttext (DB cache cosine top_k)",
            "top_k": top_k,
            "threshold": threshold,
            "corpus_size": len(_CORPUS_CACHE),
        },
    }



