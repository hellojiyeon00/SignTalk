"""
KoBART settings

모델 서버 설정(환경변수 기반):
- 모델 체크포인트 경로
- 디바이스(cpu/cuda/auto)
- generation 파라미터
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _getenv(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v is not None and v.strip() != "" else default


def _getenv_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise ValueError(f"{name} must be an int. got={raw!r}") from e


@dataclass(frozen=True)
class Settings:
    # Transformers.from_pretrained() 가 읽을 "폴더" 경로
    kobart_model_dir: str = _getenv(
    "KOBART_MODEL_DIR",
    _getenv("KOBART_CHECKPOINT", "assets/kobart/final_model_checkpoint-17800")
)

    # cuda | cpu | auto
    device: str = _getenv("DEVICE", "auto")

    # generation (KoBART 전용 env 키)
    max_new_tokens: int = _getenv_int("KOBART_MAX_NEW_TOKENS", 64)
    num_beams: int = _getenv_int("KOBART_NUM_BEAMS", 4)


settings = Settings()