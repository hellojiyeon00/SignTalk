"""
processing_20260203.py
--------------------------------------------------------------------------
Dataset Extraction Script for Sign Language Text-Gloss-Origin & Text-Gloss
--------------------------------------------------------------------------
Author: SoyoungKim
Date: 2026-02-05 => *전처리 완료
    - AWS 환경용 전처리 스크립트 구조
    - /test/corpus/2024_*/*.json
    - 1) 한국어-수어 명렬 말뭉치 데이터셋에서 Text-Gloss-Origin jsonl 추출
    - 2) Model(KoBART) 1차 학습을 위해 금융(FI) 데이터를 제외한 Text-Gloss jsonl 추출
Data: 한국수어 문장
    - 일상생활(44,337): LI
    - 금융(28,078): FI
    - 교육(20,858): ED
    - 방송(9,942): BD
Description:
    - JSON 데이터셋에서 "koreanText"와 "gloss_id" 리스트를 추출합니다.
    - 폴더 내 모든 파일을 재귀적으로 탐색하여 처리할 수 있습니다.
    - 추출 결과는 분석 및 학습이 용이하도록 .jsonl 형식으로 저장합니다.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime

# 경로 설정

# 현재 실행 중인 .py 파일의 위치
BASE_DIR = Path(__file__).resolve().parent
# 탐색 DATA의 위치
DATA_ROOT = Path("/test/corpus")
# 결과물 저장 폴더
OUTPUT_DIR = BASE_DIR.parent/"data"
LOG_DIR = BASE_DIR.parent/"logs"
# 확인용 출력
print(f"데이터 읽는 곳: {DATA_ROOT}")
print(F"결과 저장하는 곳: {OUTPUT_DIR}")

# 금융 데이터 제외 키워드
EXCLUDE_CODE = "FI"
TODAY = datetime.now().strftime("%Y%m%d")

# 결과 파일 경로 (오늘 날짜 포함)
FULL_DATA_PATH = OUTPUT_DIR/f"corpus_data_{TODAY}.jsonl"
TRAIN_READ_PATH = OUTPUT_DIR/f"corpus_train_data_{TODAY}.jsonl"
CHECKPOINT_PATH = LOG_DIR/"processed_files.txt"

# 폴더 생성 및 로깅
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR/f"preprocessing_{TODAY}.log"),
        logging.StreamHandler()
    ]
)

def extract_data_from_json(file_path: str) -> Optional[Dict]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

            # 한국어 원문 추출 (sentence)
            sentence = data.get("krlgg_sntenc", {}).get("koreanText", "")

            # 글로스 추출 (sign_script -> sign_gestures_strong)
            gestures = data.get("sign_script", {}).get("sign_gestures_strong", [])
            gloss_list = [item.get("gloss_id") for item in gestures if item.get("gloss_id")]
            gloss_sentence = " ".join(gloss_list)

            if sentence and gloss_sentence:
                return {"text": sentence, "gloss": gloss_sentence, "origin": file_path}
    
    except Exception as e:
        logging.error(f"Error: {file_path} -> {e}")
    return None

def main():
    logging.info("전체 데이터 전처리 작업을 시작합니다.")

    # 기존 체크포인트 및 결과 파일 삭제 확인 (새로 시작)
    for p in [FULL_DATA_PATH, TRAIN_READ_PATH, CHECKPOINT_PATH]:
        if os.path.exists(p):
            os.remove(p)
            logging.info(f"기존 파일 삭제됨: {p}")

    json_files = []

    # 파일 탐색 (Path.rglob을 쓰면 훨씬 빠르고 간단)
    logging.info("JSON 파일을 탐색 중입니다...")
    # rglob("*.json")은 하위 폴더의 모든 json을 찾아줌
    all_jsons = list(DATA_ROOT.rglob("*.json"))

    total_json = len(all_jsons)
    logging.info(f"탐색 완료: 총 {total_json}개의 JSON 파일을 발견했습니다.")

    success_count = 0
    excluded_count = 0

    with open(FULL_DATA_PATH, "a", encoding="utf-8") as f_full, \
        open(TRAIN_READ_PATH, "a", encoding="utf-8") as f_train, \
        open(CHECKPOINT_PATH, "a", encoding="utf-8") as f_check:

        for idx, file_path in enumerate(all_jsons):
            # 파일명에 공백이 있을 수 있으므로 처리 (Path 객체 활용)
            filename = file_path.name.strip()
            result = extract_data_from_json(str(file_path))

            if result:
                # 전체 데이터 저장
                f_full.write(json.dumps(result, ensure_ascii=False) + "\n")

                # 학습용 데이터 저장 (금융 데이터 FI 필터링)
                if EXCLUDE_CODE not in filename:
                    train_item = {"text": result["text"], "gloss": result["gloss"]}
                    f_train.write(json.dumps(train_item, ensure_ascii=False) + "\n")
                else:
                    excluded_count += 1

                # 체크포인트 기록
                f_check.write(str(file_path) + "\n")
                success_count += 1

            if (idx + 1) % 1000 == 0:
                logging.info(f"진행: {idx+1}/{total_json} (성공: {success_count}, 제외: {excluded_count})")

    logging.info("=" * 50)
    logging.info(f"최종 처리 완료: {success_count}건 성공 (금융 제외 {excluded_count}건)")
    logging.info(f"학습 가능 데이터: {success_count - excluded_count}건")
    logging.info("=" * 50)

if __name__ == "__main__":
    main()