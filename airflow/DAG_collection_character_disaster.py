"""
DAG_collection_character_disaster.py

재난문자 수집 DAG
- 2분마다 공공 API를 호출해 신규 재난문자를 PostgreSQL + Kafka에 적재
- collection_character_disaster.py 의 f_main() 을 PythonOperator로 실행
"""

import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# DAG 파일과 수집 스크립트가 같은 디렉토리(/opt/airflow/dags)에 위치
# Docker 볼륨: ./data_pipeline:/opt/airflow/dags
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from collection_character_disaster import f_main  # noqa: E402

# ── DAG 기본 설정 ─────────────────────────────────────────────────
DEFAULT_ARGS = {
    'owner':           'airflow',
    'depends_on_past': False,
    'retries':         1,
    'retry_delay':     timedelta(minutes=1),
}

# ── DAG 정의 ──────────────────────────────────────────────────────
with DAG(
    dag_id='DAG_collection_character_disaster',
    default_args=DEFAULT_ARGS,
    schedule='*/2 * * * *',      # 2분마다 실행
    start_date=datetime(2026, 2, 20),
    catchup=False,
    tags=['재난문자수집'],
) as dag:

    task_collect = PythonOperator(
        task_id='TASK_collection_character_disaster',
        python_callable=f_main,
    )

    task_collect   # 단일 태스크 DAG (확장 시 >> 로 체이닝)