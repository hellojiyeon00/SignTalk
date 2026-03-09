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
from pathlib import Path


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
    # - 우선순위: KOBART_MODEL_DIR > KOBART_CHECKPOINT
    # - 둘 다 없으면 즉시 실패(assets fallback 사용 금지)
    kobart_model_dir: str = _getenv("KOBART_MODEL_DIR", _getenv("KOBART_CHECKPOINT", ""))

    # cuda | cpu | auto
    device: str = _getenv("DEVICE", "auto")

    # generation (KoBART 전용 env 키)
    max_new_tokens: int = _getenv_int("KOBART_MAX_NEW_TOKENS", 64)
    num_beams: int = _getenv_int("KOBART_NUM_BEAMS", 4)


settings = Settings()

# env 강제: 둘 다 없으면 즉시 실패 (fallback 금지)
if settings.kobart_model_dir.strip() == "":
    raise RuntimeError("KOBART_MODEL_DIR 또는 KOBART_CHECKPOINT를 루트 .env에 설정해야 합니다.")

# 파일 경로로 들어오면 from_pretrained는 보통 폴더를 기대하므로 parent로 보정
p = Path(settings.kobart_model_dir).expanduser()
if p.exists() and p.is_file():
    object.__setattr__(settings, "kobart_model_dir", str(p.parent))

# 최종 검증: 반드시 존재하는 디렉토리여야 함
p2 = Path(settings.kobart_model_dir).expanduser()
if not p2.exists() or not p2.is_dir():
    raise FileNotFoundError(f"KoBART pretrained dir not found: {p2} (env={settings.kobart_model_dir!r})")