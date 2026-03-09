from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FastText retrieval evaluation")
    parser.add_argument(
        "--log_path",
        type=str,
        required=True,
        help="fasttext inference jsonl 로그 파일 경로",
    )
    parser.add_argument(
        "--word_list_path",
        type=str,
        required=True,
        help="DB word_name 목록 txt 파일 경로 (한 줄에 하나)",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        required=True,
        help="평가 결과 저장 디렉토리",
    )
    parser.add_argument(
        "--thresholds",
        type=float,
        nargs="*",
        default=[0.50, 0.55, 0.60, 0.65],
        help="threshold 통과율 계산 기준값들",
    )
    return parser.parse_args()


def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    value = text.strip()

    # 날짜(활용):1일후 -> 날짜
    value = re.sub(r":[^:]+$", "", value)

    # 괄호 내용 제거: (사람을)차다 -> 차다
    value = re.sub(r"\([^)]*\)", "", value)

    # 유니코드 숫자 표기 제거: 세다¹ -> 세다
    value = re.sub(r"[¹²³⁴⁵⁶⁷⁸⁹⁰]+", "", value)

    # 공백 정리
    value = re.sub(r"\s+", " ", value).strip()
    return value


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]

    values_sorted = sorted(values)
    pos = (len(values_sorted) - 1) * q
    lower = math.floor(pos)
    upper = math.ceil(pos)

    if lower == upper:
        return values_sorted[lower]

    lower_val = values_sorted[lower]
    upper_val = values_sorted[upper]
    weight = pos - lower
    return lower_val * (1 - weight) + upper_val * weight


def load_word_set(word_list_path: Path) -> tuple[set[str], set[str]]:
    raw_words: set[str] = set()
    norm_words: set[str] = set()

    with word_list_path.open("r", encoding="utf-8") as f:
        for line in f:
            word = line.strip()
            if not word:
                continue
            raw_words.add(word)
            norm = normalize_text(word)
            if norm:
                norm_words.add(norm)

    return raw_words, norm_words


def extract_fasttext_records(log_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    with log_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            if item.get("task") != "fasttext":
                continue

            result = item.get("result", {})
            results = result.get("results", {})
            meta = result.get("meta", {})

            elapsed_ms = item.get("elapsed_ms")
            tokens_len = item.get("tokens_len")
            threshold = meta.get("threshold", 0.65)

            if not isinstance(results, dict):
                continue

            for token, payload in results.items():
                if not isinstance(payload, dict):
                    continue

                candidates = payload.get("candidates", [])
                if not isinstance(candidates, list):
                    candidates = []

                top1_score = payload.get("score")
                decision = payload.get("decision")
                suggested = payload.get("suggested") or {}
                suggested_word = suggested.get("word") if isinstance(suggested, dict) else None

                candidate_words = []
                candidate_scores = []

                for cand in candidates:
                    if not isinstance(cand, dict):
                        continue
                    word = cand.get("word")
                    score = cand.get("score")
                    if isinstance(word, str):
                        candidate_words.append(word)
                    if isinstance(score, (int, float)) and not math.isnan(score):
                        candidate_scores.append(float(score))

                records.append(
                    {
                        "token": token,
                        "token_norm": normalize_text(token),
                        "top1_score": (
                            float(top1_score)
                            if isinstance(top1_score, (int, float)) and not math.isnan(top1_score)
                            else None
                            ),
                        "decision": decision,
                        "suggested_word": suggested_word,
                        "candidate_words": candidate_words,
                        "candidate_words_norm": [normalize_text(w) for w in candidate_words],
                        "candidate_scores": candidate_scores,
                        "candidate_count": len(candidate_words),
                        "elapsed_ms": float(elapsed_ms) if isinstance(elapsed_ms, (int, float)) else None,
                        "tokens_len": int(tokens_len) if isinstance(tokens_len, int) else None,
                        "threshold": float(threshold) if isinstance(threshold, (int, float)) else 0.65,
                    }
                )

    return records


def build_metrics(
    records: list[dict[str, Any]],
    raw_words: set[str],
    norm_words: set[str],
    thresholds: list[float],
) -> dict[str, Any]:
    total_tokens = len(records)

    top1_scores = [r["top1_score"] for r in records if r["top1_score"] is not None]
    elapsed_list = [r["elapsed_ms"] for r in records if r["elapsed_ms"] is not None]
    candidate_counts = [r["candidate_count"] for r in records]

    raw_exact_match_count = 0
    norm_exact_match_count = 0
    top1_raw_hit_count = 0
    top1_norm_hit_count = 0
    top10_raw_hit_count = 0
    top10_norm_hit_count = 0
    mrr_raw_sum = 0.0
    mrr_norm_sum = 0.0

    decision_counter: Counter[str] = Counter()
    top1_word_counter: Counter[str] = Counter()

    threshold_hits = {str(t): 0 for t in thresholds}

    for r in records:
        token = r["token"]
        token_norm = r["token_norm"]
        candidates = r["candidate_words"]
        candidates_norm = r["candidate_words_norm"]
        top1_score = r["top1_score"]
        decision = r["decision"]

        if isinstance(decision, str):
            decision_counter[decision] += 1

        if candidates:
            top1_word_counter[candidates[0]] += 1

        raw_match = token in raw_words
        norm_match = token_norm in norm_words if token_norm else False

        if raw_match:
            raw_exact_match_count += 1
        if norm_match:
            norm_exact_match_count += 1

        if top1_score is not None:
            for t in thresholds:
                if top1_score >= t:
                    threshold_hits[str(t)] += 1

        # raw exact-match accuracy subset
        if raw_match and candidates:
            if candidates[0] == token:
                top1_raw_hit_count += 1
            if token in candidates[:10]:
                top10_raw_hit_count += 1
                rank = candidates[:10].index(token) + 1
                mrr_raw_sum += 1.0 / rank

        # normalized exact-match accuracy subset
        if norm_match and candidates_norm:
            if candidates_norm[0] == token_norm:
                top1_norm_hit_count += 1
            if token_norm in candidates_norm[:10]:
                top10_norm_hit_count += 1
                rank = candidates_norm[:10].index(token_norm) + 1
                mrr_norm_sum += 1.0 / rank

    raw_subset = raw_exact_match_count
    norm_subset = norm_exact_match_count

    metrics = {
        "total_tokens": total_tokens,
        "db_word_count": len(raw_words),
        "basic_stats": {
            "avg_candidate_count": round(sum(candidate_counts) / total_tokens, 4) if total_tokens else 0.0,
            "avg_top1_score": round(sum(top1_scores) / len(top1_scores), 4) if top1_scores else 0.0,
            "median_top1_score": round(statistics.median(top1_scores), 4) if top1_scores else 0.0,
            "min_top1_score": round(min(top1_scores), 4) if top1_scores else 0.0,
            "max_top1_score": round(max(top1_scores), 4) if top1_scores else 0.0,
            "std_top1_score": round(statistics.pstdev(top1_scores), 4) if len(top1_scores) > 1 else 0.0,
        },
        "threshold_hit_rate": {
            k: round(v / len(top1_scores), 4) if top1_scores else 0.0
            for k, v in threshold_hits.items()
        },
        "decision_distribution": dict(decision_counter),
        "vocab_coverage": {
            "raw_exact_match_count": raw_exact_match_count,
            "raw_exact_match_rate": round(raw_exact_match_count / total_tokens, 4) if total_tokens else 0.0,
            "normalized_exact_match_count": norm_exact_match_count,
            "normalized_exact_match_rate": round(norm_exact_match_count / total_tokens, 4) if total_tokens else 0.0,
            "oov_count_raw": total_tokens - raw_exact_match_count,
            "oov_rate_raw": round((total_tokens - raw_exact_match_count) / total_tokens, 4) if total_tokens else 0.0,
            "oov_count_normalized": total_tokens - norm_exact_match_count,
            "oov_rate_normalized": round((total_tokens - norm_exact_match_count) / total_tokens, 4) if total_tokens else 0.0,
        },
        "exact_match_eval_raw": {
            "subset_size": raw_subset,
            "top1_accuracy": round(top1_raw_hit_count / raw_subset, 4) if raw_subset else 0.0,
            "recall_at_10": round(top10_raw_hit_count / raw_subset, 4) if raw_subset else 0.0,
            "mrr_at_10": round(mrr_raw_sum / raw_subset, 4) if raw_subset else 0.0,
        },
        "exact_match_eval_normalized": {
            "subset_size": norm_subset,
            "top1_accuracy": round(top1_norm_hit_count / norm_subset, 4) if norm_subset else 0.0,
            "recall_at_10": round(top10_norm_hit_count / norm_subset, 4) if norm_subset else 0.0,
            "mrr_at_10": round(mrr_norm_sum / norm_subset, 4) if norm_subset else 0.0,
        },
        "latency_ms": {
            "avg": round(sum(elapsed_list) / len(elapsed_list), 4) if elapsed_list else 0.0,
            "p50": round(percentile(elapsed_list, 0.50), 4) if elapsed_list else 0.0,
            "p95": round(percentile(elapsed_list, 0.95), 4) if elapsed_list else 0.0,
            "p99": round(percentile(elapsed_list, 0.99), 4) if elapsed_list else 0.0,
            "min": round(min(elapsed_list), 4) if elapsed_list else 0.0,
            "max": round(max(elapsed_list), 4) if elapsed_list else 0.0,
        },
        "diversity": {
            "unique_top1_words": len(top1_word_counter),
            "most_common_top1_words": top1_word_counter.most_common(20),
        },
    }

    return metrics


def main() -> None:
    args = parse_args()

    log_path = Path(args.log_path)
    word_list_path = Path(args.word_list_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_words, norm_words = load_word_set(word_list_path)
    records = extract_fasttext_records(log_path)
    metrics = build_metrics(records, raw_words, norm_words, args.thresholds)

    result_path = output_dir / "fasttext_eval_result.json"
    with result_path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print("===== FastText Evaluation Result =====")
    print(f"Total Tokens: {metrics['total_tokens']}")
    print(f"DB Words: {metrics['db_word_count']}")
    print(f"Avg Top1 Score: {metrics['basic_stats']['avg_top1_score']}")
    print(f"Raw Exact Match Rate: {metrics['vocab_coverage']['raw_exact_match_rate']}")
    print(f"Normalized Exact Match Rate: {metrics['vocab_coverage']['normalized_exact_match_rate']}")
    print(f"Raw Top1 Accuracy: {metrics['exact_match_eval_raw']['top1_accuracy']}")
    print(f"Normalized Top1 Accuracy: {metrics['exact_match_eval_normalized']['top1_accuracy']}")
    print(f"Raw Recall@10: {metrics['exact_match_eval_raw']['recall_at_10']}")
    print(f"Normalized Recall@10: {metrics['exact_match_eval_normalized']['recall_at_10']}")
    print(f"Normalized MRR@10: {metrics['exact_match_eval_normalized']['mrr_at_10']}")
    print(f"Avg Latency(ms): {metrics['latency_ms']['avg']}")
    print(f"P95 Latency(ms): {metrics['latency_ms']['p95']}")
    print(f"Saved: {result_path}")


if __name__ == "__main__":
    main()
