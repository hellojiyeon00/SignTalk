from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent.parent
RESULT_FILE = BASE_DIR / "evaluation/kobart_eval_result.json"
OUT_FILE = BASE_DIR / "evaluation/kobart_eval_metrics.png"


def main() -> None:
    with RESULT_FILE.open("r", encoding="utf-8") as f:
        result = json.load(f)

    metrics = {
        "BLEU": result["bleu"] / 100.0,
        "ROUGE-1": result["rouge1"],
        "ROUGE-2": result["rouge2"],
        "ROUGE-L": result["rougeL"],
        "Exact Match": result["exact_match"],
    }

    names = list(metrics.keys())
    values = list(metrics.values())
    colors = ["#2C7FB8"] * len(values)

    plt.figure(figsize=(8, 5))
    bars = plt.bar(names, values, color=colors)

    plt.ylim(0, 1.0)
    plt.ylabel("Score")
    plt.title("KoBART Evaluation Metrics")
    plt.grid(axis="y", linestyle="--", alpha=0.4)

    for bar, value in zip(bars, values):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.015,
            f"{value:.4f}",
            ha="center",
            va="bottom"
        )

    plt.tight_layout()
    plt.savefig(OUT_FILE, dpi=300)
    plt.close()
    print(f"[INFO] saved -> {OUT_FILE}")


if __name__ == "__main__":
    main()
    