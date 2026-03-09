from __future__ import annotations

import json
from pathlib import Path

import evaluate


BASE_DIR = Path(__file__).resolve().parent.parent

PRED_FILE = BASE_DIR / "assets/kobart/data_set/kobart_test_predictions.jsonl"
OUT_FILE = BASE_DIR / "evaluation/kobart_eval_result.json"


def load_predictions(path: Path) -> tuple[list[str], list[str]]:
    refs: list[str] = []
    preds: list[str] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            row = json.loads(line)

            ref = row.get("reference", "").strip()
            pred = row.get("prediction", "").strip()

            if ref and pred:
                refs.append(ref)
                preds.append(pred)

    return refs, preds


def main() -> None:
    print(f"[INFO] pred_file={PRED_FILE}")

    refs, preds = load_predictions(PRED_FILE)

    if not refs:
        raise ValueError("평가 데이터가 없습니다.")
    
    print(f"[INFO] samples={len(refs)}")

    bleu = evaluate.load("sacrebleu")
    rouge = evaluate.load("rouge")

    bleu_result = bleu.compute(predictions=preds, references=[[r] for r in refs])

    rouge_result = rouge.compute(predictions=preds, references=refs)

    exact_match = sum(int(p == r) for p, r in zip(preds, refs)) / len(refs)

    print("\n===== KoBART Evaluation Result =====")
    print(f"Samples: {len(refs)}")
    print(f"BLEU: {bleu_result['score']:.4f}")
    print(f"ROUGE-1: {rouge_result['rouge1']:.4f}")
    print(f"ROUGE-2: {rouge_result['rouge2']:.4f}")
    print(f"ROUGE-L: {rouge_result['rougeL']:.4f}")
    print(f"Exact Match: {exact_match:.4f}")

    result = {
    "samples": len(refs),
    "bleu": bleu_result["score"],
    "rouge1": rouge_result["rouge1"],
    "rouge2": rouge_result["rouge2"],
    "rougeL": rouge_result["rougeL"],
    "exact_match": exact_match,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n[INFO] evaluation result saved -> {OUT_FILE}")


if __name__ == "__main__":
    main()

