import os
import json
from datetime import datetime
from pathlib import Path

# Text2Sign 기준 경로
BASE_DIR = Path(__file__).resolve().parents[1]

# 로그 디렉토리
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 기본 로그 파일 이름 (환경변수로 override 가능)
BASE_LOG_NAME = os.getenv("MODEL_INFER_LOG", "model_infer")

# 날짜별 로그 파일
def get_log_file():
    today = datetime.now().strftime("%Y-%m-%d")
    return LOG_DIR / f"{BASE_LOG_NAME}_{today}.jsonl"


def write_jsonl_log(data: dict):
    record = {
        "timestamp": datetime.now().isoformat(),
        **data
    }

    try:
        log_file = get_log_file()

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    except Exception as e:
        print(f"[JSONL LOG ERROR] {e}")