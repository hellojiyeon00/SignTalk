# data_pipeline/Dockerfile
# apache/airflow 공식 이미지에 DAG 실행용 패키지 추가
FROM apache/airflow:2.9.2

USER airflow

COPY airflow/requirements.txt /tmp/requirements-dag.txt
RUN pip install --no-cache-dir -r /tmp/requirements-dag.txt
