import json
import math
import os
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg2
from dotenv import load_dotenv
from kafka import KafkaProducer

load_dotenv()

# ── API 설정 ───────────────────────────────────────────────────────
SERVICE_KEY = os.getenv('DISASTER_SERVICE_KEY')
BASE_URL     = 'https://www.safetydata.go.kr/V2/api/DSSP-IF-00247'
NUM_OF_ROWS  = 10

# ── DB 설정 (.env 기반) ────────────────────────────────────────────
DB_HOST     = os.getenv('DB_HOST', 'localhost')
DB_PORT     = int(os.getenv('DB_PORT', 5432))
DB_NAME     = os.getenv('DB_NAME', 'multicampus_db')
DB_USER     = os.getenv('DB_USER', 'multicampus_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# ── Kafka 설정 (.env 기반) ─────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
KAFKA_TOPIC             = 'Topic_characters'


# ── 유틸 함수 ──────────────────────────────────────────────────────

def f_now():
    """현재 시각을 KST 문자열로 반환"""
    return datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')


def f_parse_timestamp(a_value):
    """API 응답의 날짜 문자열을 datetime으로 변환 (None 안전)
    API가 'YYYY/MM/DD HH:MM:SS' 또는 'YYYY-MM-DD HH:MM:SS' 두 형식 모두 반환함
    """
    if a_value is None:
        return None
    v_value = str(a_value).strip()
    if not v_value:
        return None
    if '.' in v_value:
        v_value = v_value.split('.')[0]
    # 슬래시 형식을 대시 형식으로 통일
    v_value = v_value.replace('/', '-')
    return datetime.strptime(v_value, '%Y-%m-%d %H:%M:%S')


def f_strip_or_null(a_value):
    """공백 문자열을 None으로 정규화"""
    if a_value is None:
        return None
    v_value = str(a_value).strip()
    return v_value if v_value else None


def f_classify_type(a_emrg_step_nm):
    """재난 단계명 → 재난 유형 코드 분류
    EX: 위급재난 / EM: 긴급재난 / SA: 안전안내 / NO: 미분류
    """
    if a_emrg_step_nm is None:
        return 'NO'
    if '위급재난' in a_emrg_step_nm:
        return 'EX'
    if '긴급재난' in a_emrg_step_nm:
        return 'EM'
    if '안전안내' in a_emrg_step_nm:
        return 'SA'
    return 'NO'


def f_exists(a_cursor, a_msg_cn):
    """동일한 재난문자가 DB에 이미 존재하는지 확인"""
    v_sql = """
        SELECT 1
        FROM multicampus_schema.characters
        WHERE character_content = %s
        LIMIT 1
    """
    a_cursor.execute(v_sql, (a_msg_cn,))
    return a_cursor.fetchone() is not None


# ── API 호출 ───────────────────────────────────────────────────────

def f_call_api(a_page_no, a_num_of_rows):
    """재난문자 공공 API 호출 후 JSON 반환"""
    v_params = {
        'serviceKey': SERVICE_KEY,
        'returnType': 'json',
        'pageNo':     str(a_page_no),
        'numOfRows':  str(a_num_of_rows),
    }
    v_url = f'{BASE_URL}?{urllib.parse.urlencode(v_params)}'
    with urllib.request.urlopen(v_url, timeout=20) as v_resp:
        v_data = v_resp.read().decode('UTF-8', errors='replace')
    return json.loads(v_data)


def f_get_last_page_no():
    """전체 건수를 조회해 마지막 페이지 번호 계산"""
    v_json = f_call_api(1, 1)
    if v_json.get('header', {}).get('resultCode') != '00':
        raise Exception(f'API 오류: {v_json}')
    v_total_count = v_json.get('totalCount', 0)
    if v_total_count == 0:
        return 1
    return math.ceil(v_total_count / NUM_OF_ROWS)


# ── Kafka ──────────────────────────────────────────────────────────

def f_get_kafka_producer():
    """Kafka 프로듀서 생성 (UTF-8 JSON 직렬화)"""
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('UTF-8'),
    )


# ── DB 저장 ────────────────────────────────────────────────────────

INSERT_SQL = """
    INSERT INTO multicampus_schema.characters (
        character_type_code,
        character_content,
        create_user,
        disaster_sn,
        disaster_crt_dt,
        disaster_rcptn_rgn_nm,
        disaster_emrg_step_nm,
        disaster_dst_se_nm,
        disaster_reg_ymd,
        disaster_mdfcn_ymd
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def f_insert_db(a_records):
    """레코드를 PostgreSQL에 INSERT하고 Kafka로 발행. 삽입 건수 반환."""
    if not a_records:
        return 0

    v_producer = f_get_kafka_producer()
    v_conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
    )
    v_count = 0

    try:
        with v_conn:
            with v_conn.cursor() as v_cursor:
                for v_rec in a_records:
                    v_msg_cn = v_rec.get('MSG_CN')
                    if v_msg_cn is None:
                        continue
                    if f_exists(v_cursor, v_msg_cn):
                        continue

                    v_type_code           = f_classify_type(v_rec.get('EMRG_STEP_NM'))
                    v_disaster_sn         = v_rec.get('SN')
                    v_disaster_crt_dt     = f_parse_timestamp(v_rec.get('CRT_DT'))
                    v_rcptn_rgn_nm        = f_strip_or_null(v_rec.get('RCPTN_RGN_NM'))
                    v_emrg_step_nm        = f_strip_or_null(v_rec.get('EMRG_STEP_NM'))
                    v_dst_se_nm           = f_strip_or_null(v_rec.get('DST_SE_NM'))
                    v_disaster_reg_ymd    = f_parse_timestamp(v_rec.get('REG_YMD'))
                    v_disaster_mdfcn_ymd  = f_parse_timestamp(v_rec.get('MDFCN_YMD'))

                    v_cursor.execute(INSERT_SQL, (
                        v_type_code,
                        v_msg_cn,
                        'cci10000',
                        v_disaster_sn,
                        v_disaster_crt_dt,
                        v_rcptn_rgn_nm,
                        v_emrg_step_nm,
                        v_dst_se_nm,
                        v_disaster_reg_ymd,
                        v_disaster_mdfcn_ymd,
                    ))

                    v_producer.send(KAFKA_TOPIC, {
                        'character_type_code':    v_type_code,
                        'character_content':      v_msg_cn,
                        'disaster_sn':            v_disaster_sn,
                        'disaster_crt_dt':        str(v_disaster_crt_dt),
                        'disaster_rcptn_rgn_nm':  v_rcptn_rgn_nm,
                        'disaster_emrg_step_nm':  v_emrg_step_nm,
                        'disaster_dst_se_nm':     v_dst_se_nm,
                        'disaster_reg_ymd':       str(v_disaster_reg_ymd),
                        'disaster_mdfcn_ymd':     str(v_disaster_mdfcn_ymd),
                    })
                    v_count += 1
    finally:
        v_producer.flush()
        v_producer.close()
        v_conn.close()

    return v_count


# ── 메인 ───────────────────────────────────────────────────────────

def f_main():
    print(f'[{f_now()}] Disaster Collector Start!')
    try:
        v_last_page_no = f_get_last_page_no()
        v_json = f_call_api(v_last_page_no, NUM_OF_ROWS)

        if v_json.get('header', {}).get('resultCode') != '00':
            print(f'API 응답 오류: {v_json}')
            return

        v_records  = v_json.get('body') or []
        v_inserted = f_insert_db(v_records)

        print(f'Last Page : {v_last_page_no}')
        print(f'Fetched   : {len(v_records)}')
        print(f'Inserted  : {v_inserted}')

    except Exception as e:
        print(f'ERROR : {e}')

    print(f'[{f_now()}] End!!')


if __name__ == '__main__':
    f_main()
