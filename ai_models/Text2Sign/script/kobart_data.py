import json
from pathlib import Path

# --- 설정 ---
# 실제 생성된 전체 데이터 파일명으로 수정해주세요
INPUT_FILE = "data/corpus_data_20260205.jsonl" 
TRAIN_OUTPUT_FILE = "data/kobart_data.jsonl"

EXCLUDE_KEYWORD = "FI" # 폴더명에 포함된 금융 코드

success_count = 0
excluded_count = 0

print(f"🚀 KoBART 학습용 데이터 정제 시작...")

with open(INPUT_FILE, "r", encoding="utf-8") as f_in, \
     open(TRAIN_OUTPUT_FILE, "w", encoding="utf-8") as f_out:
    
    for line in f_in:
        try:
            data = json.loads(line)
            
            # 1. origin 경로를 대문자로 변환하여 FI 폴더 포함 여부 확인
            # (data['origin']에 폴더명이 포함된 전체 경로가 들어있으므로 가능합니다)
            origin_path = data.get("origin", "").upper()
            
            if EXCLUDE_KEYWORD in origin_path:
                excluded_count += 1
                continue # 금융 데이터는 학습용 파일에 쓰지 않고 건너뜀
            
            # 2. 금융이 아닌 데이터만 'text'와 'gloss'만 뽑아서 저장
            train_item = {
                "text": data["text"],
                "gloss": data["gloss"]
            }
            f_out.write(json.dumps(train_item, ensure_ascii=False) + "\n")
            success_count += 1
            
        except json.JSONDecodeError:
            continue

print("=" * 50)
print(f"✅ 정제 완료!")
print(f"- 원본 통합 데이터: {success_count + excluded_count}건 (유지)")
print(f"- 제외된 금융(FI) 데이터: {excluded_count}건 (폴더명 기준)")
print(f"- 최종 KoBART 학습 데이터: {success_count}건")
print(f"- 저장 위치: {TRAIN_OUTPUT_FILE}")
print("=" * 50)