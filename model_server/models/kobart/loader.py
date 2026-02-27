"""
models.kobart.loader

Loads tokenizer/model once and returns a bundle dict.
- 환경변수 KOBART_CHECKPOINT에서 체크포인트 경로를 읽는다.
- 프로세스 내 1회 로드(전역 캐시)로 모델 충돌/중복 로드를 방지한다.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from .settings import settings


_MODEL_BUNDLE: Optional[Dict[str, Any]] = None


def get_model_bundle() -> Dict[str, Any]:
    """
    tokenizer/model을 1회 로드하고 bundle(dict)로 반환한다.
    """
    global _MODEL_BUNDLE
    if _MODEL_BUNDLE is not None:
        return _MODEL_BUNDLE

    checkpoint_path = settings.kobart_model_dir
    if not checkpoint_path or not str(checkpoint_path).strip():
        raise RuntimeError("KoBART checkpoint path is empty (KOBART_MODEL_DIR/KOBART_CHECKPOINT)")

    ckpt_dir = Path(checkpoint_path).expanduser().resolve()
    if not ckpt_dir.exists():
        raise RuntimeError(f"Checkpoint path not found: {ckpt_dir}")

    # device 정책: cpu | cuda | auto
    dev_opt = (settings.device or "auto").strip().lower()
    if dev_opt == "cpu":
        device = "cpu"
    elif dev_opt == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("DEVICE=cuda but CUDA is not available")
        device = "cuda"
    else:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    tokenizer = AutoTokenizer.from_pretrained(str(ckpt_dir))
    model = AutoModelForSeq2SeqLM.from_pretrained(str(ckpt_dir)).to(device)
    model.eval()

    _MODEL_BUNDLE = {
        "tokenizer": tokenizer,
        "model": model,
        "device": device,
        "model_name": os.environ.get("MODEL_NAME", "kobart"),
        "model_dir": str(ckpt_dir),
    }
    return _MODEL_BUNDLE
