"""
models.kobart.generate

Runs generation and returns gloss string.
(기존 inference/generate.py를 멀티 모델 구조에 맞게 이식)
"""

from __future__ import annotations

import logging

import torch

logger = logging.getLogger(__name__)


@torch.inference_mode()
def generate_gloss(
    bundle: dict,
    text: str,
    top_k: int = 1,
    max_new_tokens: int = 256,
    num_beams: int = 4
) -> str:
    logger.info("[GEN ENTER] models/kobart/generate.py generate_gloss called")

    tokenizer = bundle["tokenizer"]
    model = bundle["model"]
    device = bundle["device"]

    # 1단계: 토크나이즈 (CPU, 원본 상태)
    enc = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512
    )

    # 디버그: 입력이 잘렸는지 확인
    input_ids = enc["input_ids"][0]
    head = tokenizer.decode(input_ids[:80], skip_special_tokens=False)
    tail = tokenizer.decode(input_ids[-80:], skip_special_tokens=False)

    logger.info(
        "[GET DEBUG] chars=%d tokens=%d head=%s tail=%s",
        len(text),
        input_ids.shape[0],
        head.replace("\n", " "),
        tail.replace("\n", " "),
    )

    # 2단계: 모델 입력용으로 정리 (GPU/CPU)
    # KoBART(BART)는 token_type_ids를 보통 사용하지 않음
    enc.pop("token_type_ids", None)
    enc = {k: v.to(device) for k, v in enc.items()}

    outputs = model.generate(
        **enc,
        max_new_tokens=max_new_tokens,
        num_beams=num_beams,
        num_return_sequences=top_k,
        early_stopping=True,
    )

    # top_k=1 기준
    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return decoded.strip()


# 참고(디버깅용 메모)
# 1단계: 토크나이즈 (CPU, 원본 상태)
# enc = tokenizer(
#     text,
#     return_tensors="pt",
#     truncation=True,
#     max_length=512
# )
#
# # 🔎 여기서 자유롭게 디버깅 가능
# print("token_len =", enc["input_ids"].shape[1])
# print("tail =", tokenizer.decode(enc["input_ids"][0][-50:]))
#
# # 2단계: 모델 입력용으로 정리
# enc.pop("token_type_ids", None)
# model_inputs = {k: v.to(device) for k, v in enc.items()}
