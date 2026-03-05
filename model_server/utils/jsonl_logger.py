import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]  # model_server
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "model_infer.jsonl"

LOG_DIR.mkdir(parents=True, exist_ok=True)


def write_jsonl_log(data: dict):

    record = {
        "timestamp": datetime.now().isoformat(),
        **data
    }

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[JSONL LOG ERROR] {e}")
        