"""
Split KoBART dataset (full.jsonl) into train/valid/test JSONL files.

Input schema (one JSON object per line):
  - {"text": "...", "gloss": "..."}  (your current dataset)
  - {"src": "...", "tgt": "..."}     (accepted as well)

Internal/output schema:
  {"src": "...", "tgt": "..."}

Policy:
- Deduplicate exact duplicates by (src, tgt)
- Drop invalid/empty records
- Shuffle with fixed seed for reproducibility
- Split ratios: train=0.8, valid=0.1, test=0.1
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Dict, List, Tuple

def load_jsonl(path: Path) -> Tuple[List[Dict[str, str]], int]:
    """
    Load JSONL records and normalize keys to {"src","tgt"}.

    Returns:
      (records, bad_lines)
    """
    records: List[Dict[str, str]] = []
    bad_lines = 0

    with path.open("r", encoding="utf-8") as f:
        for _, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                bad_lines += 1
                continue

            src = str(obj.get("src", obj.get("text", ""))).strip()
            tgt = str(obj.get("tgt", obj.get("gloss", ""))).strip()
            if not src or not tgt:
                continue

            # ✅ append dict (not list)
            records.append({"src": src, "tgt": tgt})

    return records, bad_lines

def deduplicate(records: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], int]:
    """Remove exact duplicate pairs (src, tgt). Returns (unique_records, removed_count)."""
    seen = set()
    unique: List[Dict[str, str]] = []
    for r in records:
        key = (r["src"], r["tgt"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique, (len(records) - len(unique))

def write_jsonl(path: Path, records: List[Dict[str, str]]) -> None:
    """Write records to JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def split_records(
    records: List[Dict[str, str]],
    train_ratio: float,
    valid_ratio: float,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
    """Split into train/valid/test by ratios; test gets the remainder."""
    n = len(records)
    n_train = int(n * train_ratio)
    n_valid = int(n * valid_ratio)
    train = records[:n_train]
    valid = records[n_train : n_train + n_valid]
    test = records[n_train + n_valid :]
    return train, valid, test

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="ml/kobart/data/full.jsonl")
    parser.add_argument("--out_dir", type=str, default="ml/kobart/data")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train_ratio", type=float, default=0.8)
    parser.add_argument("--valid_ratio", type=float, default=0.1)
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.out_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    records, bad_lines = load_jsonl(input_path)
    records, removed = deduplicate(records)

    rng = random.Random(args.seed)
    rng.shuffle(records)

    train, valid, test = split_records(records, args.train_ratio, args.valid_ratio)

    write_jsonl(out_dir / "train.jsonl", train)
    write_jsonl(out_dir / "valid.jsonl", valid)
    write_jsonl(out_dir / "test.jsonl", test)

    print(f"Input: {input_path}")
    print(f"Bad JSON lines skipped: {bad_lines}")
    print(f"Total records: {len(records)} (dedup removed: {removed})")
    print(f"Train: {len(train)}")
    print(f"Valid: {len(valid)}")
    print(f"Test : {len(test)}")
    print("Done.")

if __name__ == "__main__":
    main()