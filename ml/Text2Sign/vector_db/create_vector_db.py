"""
creat_vector_db.py
------------------------------------------------------------
Docstring for sign-language-project.scripts.create_vector_db
------------------------------------------------------------
date: 2026-02-03
Author: SoyoungKim
"""

import csv
import json
import os
import numpy as np
# from gensim.models.fasttext import load_facebook_model
from gensim.models.fasttext import load_facebook_vectors

# 경로 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

# 입력 파일 경로
MODEL_PATH = os.path.join(BASE_DIR, "data", "cc.ko.300.bin")
CSV_INPUT = os.path.join(BASE_DIR, "data", "sign_mp4_url.csv")
# 출력 파일 경로 (data 폴더 내부에 저장)
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "create_vector_db.json")

def main():
    # 사전 학습된 모델 로드
    if not os.path.exists(MODEL_PATH):
        print(f"에러: 모델 파일을 찾을 수 없습니다.: {MODEL_PATH}")
        return
    
    # print("사전 학습된 FastText 모델 로드 중...")
    print("FastText 벡터 엔진 로드 중 (메모리 절약 모드)...")

    try:
        # co.ko.300.bin load
        model = load_facebook_vectors(MODEL_PATH)
        print("벡터 로드 완료!")
    except Exception as e:
        print(f"모델 로드 중 오류 발생: {e}")
        return

    # CSV 파일 읽기 및 벡터 추출
    if not os.path.exists(CSV_INPUT):
        print(f"에러: CSV 파일을 찾을 수 없습니다: {CSV_INPUT}")
        return
    
    word_db = []
    # 중복 체크를 위한 집합 생성
    seen_data = set()
    count = 0
    print(f"{CSV_INPUT} 데이터 처리 시작...")

    with open(CSV_INPUT, "r", encoding="utf-8") as f:
        reader = csv.reader(f)

        # 헤더가 있다면 건너뜀 (word, video_url...)
        try:
            header = next(reader)
        except StopIteration:
            print(f"파일이 비어있습니다.")
            return

        for row in reader:
            if not row or len(row) < 2:
                continue

            # CSV 컬럼 매핑: word(0), video_url(1)
            word = row[0].strip()
            url = row[1].strip()

            # 단어와 URL의 조합을 하나의 키로 생성
            # 단어와 URL이 모두 같을 때만 중복으로 간주함
            data_key = (word, url)

            if data_key in seen_data:
                # 이미 처리한 데이터라면 건너뜀
                continue

            try:
                # FastText 300차원 벡터 추출 (numpy array -> list 변환)
                # [참고] 사전에 없는 단어라도 FastText는 n-gram을 통해 벡터를 생성해줌
                # vector = model.wv[word].tolist()
                vector = model[word].tolist()

                word_db.append({
                    "word": word,
                    "url": url,
                    "vector": vector
                })

                # 처리 완료된 데이터 기록
                seen_data.add(data_key)
                count += 1

                if count % 1000 == 0:
                    print(f"진행 중... {count}개 단어 처리 완료")

            except Exception as e:
                # KeyError 등이 발생할 경우를 대비한 예외처리
                print(f"단어 {word} 처리 중 오류: {e}")

    # 결과 저장
    print(f"결과 저장 중: {OUTPUT_PATH}")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(word_db, f, ensure_ascii=False, indent=4)

    print("-" * 30)
    print(f"작업 성공! 총 {len(word_db)}개의 단어-벡터 세트가 생성되었습니다.")

if __name__ == "__main__":
    main()

# 전체 모델 구조를 파싱하지 않고 단어와 숫자(벡터) 테이블만 읽어옴