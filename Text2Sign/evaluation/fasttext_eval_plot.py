from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent.parent
RESULT_FILE = BASE_DIR / "evaluation/fasttext_eval_result.json"

METRICS_OUT_FILE = BASE_DIR / "evaluation/fasttext_eval_metrics.png"
LATENCY_OUT_FILE = BASE_DIR / "evaluation/fasttext_eval_latency.png"


def load_result() -> dict:
    with RESULT_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def plot_quality_metrics(result: dict) -> None:
    metrics = {
        "Avg Top1\nScore": result["basic_stats"]["avg_top1_score"],
        "Threshold\n≥ 0.5": result["threshold_hit_rate"]["0.5"],
        "Threshold\n≥ 0.55": result["threshold_hit_rate"]["0.55"],
        "Threshold\n≥ 0.6": result["threshold_hit_rate"]["0.6"],
        "Norm Exact\nMatch": result["vocab_coverage"]["normalized_exact_match_rate"],
    }

    names = list(metrics.keys())
    values = list(metrics.values())
    colors = ["#2C7FB8", "#41B6C4", "#41B6C4", "#41B6C4", "#BDBDBD"]

    plt.figure(figsize=(8, 5))
    bars = plt.bar(names, values, color=colors)

    plt.ylim(0, 1.0)
    plt.ylabel("Score")
    plt.title("FastText Evaluation Metrics")
    plt.grid(axis="y", linestyle="--", alpha=0.4)

    for bar, value in zip(bars, values):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.015,
            f"{value:.4f}",
            ha="center",
            va="bottom",
        )

    plt.tight_layout()
    plt.savefig(METRICS_OUT_FILE, dpi=300)
    plt.close()
    print(f"[INFO] saved -> {METRICS_OUT_FILE}")


def plot_latency_metrics(result: dict) -> None:
    latency = result["latency_ms"]

    metrics = {
        "P50": latency["p50"],
        "P95": latency["p95"],
        "Avg": latency["avg"],
    }

    names = list(metrics.keys())
    values = list(metrics.values())
    colors = ["#F28E2B", "#F28E2B", "#F6BE8A"]

    plt.figure(figsize=(7, 5))
    bars = plt.bar(names, values, color=colors)

    plt.ylabel("Latency (ms)")
    plt.title("FastText Latency Metrics")
    plt.grid(axis="y", linestyle="--", alpha=0.4)

    y_max = max(values) * 1.2 if values else 1.0
    plt.ylim(0, y_max)

    for bar, value in zip(bars, values):
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            value + (y_max * 0.02),
            f"{value:.1f}",
            ha="center",
            va="bottom",
        )

    plt.tight_layout()
    plt.savefig(LATENCY_OUT_FILE, dpi=300)
    plt.close()
    print(f"[INFO] saved -> {LATENCY_OUT_FILE}")


def main() -> None:
    result = load_result()
    plot_quality_metrics(result)
    plot_latency_metrics(result)


if __name__ == "__main__":
    main()
    