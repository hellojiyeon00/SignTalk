"""
역할
- URL로 들어온 task 문자열을 "handler 함수"로 매핑한다.
- main.py는 get_handler(task)로 함수만 받아서 실행한다.
- 모델 추가/삭제 시 이 파일만 수정하면 되게 만드는 것이 목표.

규칙
- handler 시그니처: infer(req: dict) -> dict
- req는 main.py에서 받은 요청을 dict로 변환한 값(text/payload 등 포함)
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

# models/ 아래에 있는 각 모델 모듈 (infer(req) 제공)
from Text2Sign.models import kobart, fasttext

Handler = Callable[[dict], dict]

# task -> handler 매핑 테이블
_HANDLERS: Dict[str, Handler] = {
    "kobart": kobart.infer,
    "fasttext": fasttext.infer
}


def get_handler(task: str) -> Optional[Handler]:
    """
    task 문자열에 해당하는 handler를 반환한다.
    없으면 None.
    """
    return _HANDLERS.get(task)


def list_tasks() -> list[str]:
    """
    현재 등록된 task 목록 반환 (디버깅/문서화용).
    """
    return sorted(_HANDLERS.keys())
