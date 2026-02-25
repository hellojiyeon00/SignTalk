"""
Gloss Preprocessor

Model Server가 반환한 gloss 문자열을 URL 매핑 전에 정제한다.

- f:1 같은 시간/프레임 토큰은 보존
- # 같은 기호 제거
- 일반 토큰에 붙은 숫자 제거 (예: 지시1 -> 지시)
- 토큰 끝 구두점 제거(예: 오늘, -> 오늘)  ← 매핑률 개선
- 공백 정리
"""

import re

_DIGITS_AT_END = re.compile(r"\d+$")
_TIME_TOKEN = re.compile(r"^f:\d+$")

# 토큰 끝 구두점(ASCII + 자주 나오는 유니코드 일부)
_TRAIL_PUNCT = re.compile(r"[.,;:!?\"'\)\]\}…]+$")


def clean_gloss(gloss: str) -> str:
    """
    모델 서버가 반환한 gloss 문자열을 URL 매핑 전에 정제합니다.

    처리 규칙:
    1) 공백 기준 토큰화
    2) '#' 제거
    3) 시간/프레임 토큰(f:1 등)은 보존 (끝 구두점 제거 후 판정)
    4) 일반 토큰은 (끝 구두점 제거 → 끝 숫자 제거) 순서로 정제
    5) 빈 토큰 제거 후 공백으로 재결합
    """
    if not isinstance(gloss, str):
        raise ValueError("gloss must be a string")

    gloss = gloss.strip()
    if not gloss:
        return ""

    tokens = gloss.split()
    out: list[str] = []

    for tok in tokens:
        tok = tok.replace("#", "").strip()
        if not tok:
            continue

        # 공통: 토큰 끝 구두점 제거(시간 토큰 판정/일반 토큰 정제 모두에 사용)
        tok_no_punct = _TRAIL_PUNCT.sub("", tok).strip()
        if not tok_no_punct:
            continue

        # 시간 토큰: f:1 등은 보존
        if tok_no_punct.startswith("f:") and _TIME_TOKEN.match(tok_no_punct):
            out.append(tok_no_punct)
            continue

        # 일반 토큰: 끝 숫자 제거 (예: 지시1 -> 지시)
        tok_clean = _DIGITS_AT_END.sub("", tok_no_punct).strip()
        if tok_clean:
            out.append(tok_clean)

    dedup: list[str] = []
    for tok in out:
        if dedup:
            prev = dedup[-1]

            if tok.startswith(prev) and tok != prev:
                rest = tok[len(prev):]

                # rest가 짧고(노이즈) 또는 동일 패턴 반복이면 제거
                # - "하세요하세요"처럼 동일 청크 반복을 잡기 위해 2글자 이상 반복 체크
                if len(rest) <= 6:
                    continue

                # 간단 반복 패턴(예: '하세요' 반복) 탐지
                if len(rest) % 2 == 0:
                    half = rest[: len(rest)//2]
                    if half and half * 2 == rest:
                        continue

        dedup.append(tok)

    return " ".join(dedup)
