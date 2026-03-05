import urllib.request
import urllib.parse
import psycopg2
import json
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from kafka import KafkaProducer
v_service_key = '2A5TIEB9124AU48F'
v_base_url = 'https://www.safetydata.go.kr/V2/api/DSSP-IF-00247'
v_db_host = '56.155.47.51'
v_db_port = 5432
v_db_name = 'multicampus_db'
v_db_user = 'multicampus_user'
v_db_password = 'multicampuscci4'
v_num_of_rows = 1000
def f_main():
   print(f'[{f_now()}] Disaster Collector Start!')
   try:
      v_last_page_no = f_get_last_page_no()
      v_json = f_call_api(v_last_page_no,v_num_of_rows)
      if v_json.get('header',{}).get('resultCode') != '00':
         print(v_json)
         return

#      v_records = v_json.get('body',[])

      v_records = v_json.get('body') or []


      v_inserted = f_insert_db(v_records)
      print(f'Last Page : {v_last_page_no}')
      print(f'Fetched : {len(v_records)}')
      print(f'Inserted : {v_inserted}')
   except Exception as E:
      print(f'ERROR : {str(E)}')
   print(f'[{f_now()}] End!!')
def f_now():
   v_now = datetime.now(ZoneInfo('Asia/Seoul'))
   return v_now.strftime('%Y/%m/%d %H:%M:%S')
def f_get_last_page_no():
   v_json = f_call_api(1,1)
   if v_json.get('header',{}).get('resultCode') != '00':
      raise Exception(str(v_json))
   v_total_count = v_json.get('totalCount',0)
   if v_total_count == 0:
      return 1
   return math.ceil(v_total_count / v_num_of_rows)
def f_call_api(a_page_no,a_num_of_rows):
   v_params = {'serviceKey':v_service_key,'returnType':'json','pageNo':str(a_page_no),'numOfRows':str(a_num_of_rows)}
   v_query = urllib.parse.urlencode(v_params)
   v_url = f'{v_base_url}?{v_query}'
   with urllib.request.urlopen(v_url,timeout=20) as v_urlopen:
      v_data = v_urlopen.read().decode('UTF-8',errors='replace')
   return json.loads(v_data)
def f_insert_db(a_records):
   if len(a_records) == 0:
      return 0
   v_producer = f_get_kafka_producer()
   v_conn = psycopg2.connect(host=v_db_host,port=v_db_port,dbname=v_db_name,user=v_db_user,password=v_db_password)
   v_insert_sql = """INSERT INTO multicampus_schema.characters
                     (character_type_code,
                      character_content,
                      create_user,
                      disaster_sn,
                      disaster_crt_dt,
                      disaster_rcptn_rgn_nm,
                      disaster_emrg_step_nm,
                      disaster_dst_se_nm,
                      disaster_reg_ymd,
                      disaster_mdfcn_ymd)
                     VALUES (%s,
                             %s,
                             %s,
                             %s,
                             %s,
                             %s,
                             %s,
                             %s,
                             %s,
                             %s)"""
   v_count = 0
   with v_conn:
      with v_conn.cursor() as v_cursor:
         for v_rec in a_records:
            v_msg_cn = v_rec.get('MSG_CN')
            if v_msg_cn is None:
               continue
            if f_exists(v_cursor,v_msg_cn):
               continue
            v_character_type_code = f_classify_type(v_rec.get('EMRG_STEP_NM'))
            v_disaster_sn = v_rec.get('SN')
            v_disaster_crt_dt = f_parse_timestamp(v_rec.get('CRT_DT'))
            v_disaster_rcptn_rgn_nm = f_strip_or_null(v_rec.get('RCPTN_RGN_NM'))
            v_disaster_emrg_step_nm = f_strip_or_null(v_rec.get('EMRG_STEP_NM'))
            v_disaster_dst_se_nm = f_strip_or_null(v_rec.get('DST_SE_NM'))
            v_disaster_reg_ymd = f_parse_timestamp(v_rec.get('REG_YMD'))
            v_disaster_mdfcn_ymd = f_parse_timestamp(v_rec.get('MDFCN_YMD'))
            v_cursor.execute(v_insert_sql,(v_character_type_code,
                                                v_msg_cn,
                                                'cci10000',
                                                v_disaster_sn,
                                                v_disaster_crt_dt,
                                                v_disaster_rcptn_rgn_nm,
                                                v_disaster_emrg_step_nm,
                                                v_disaster_dst_se_nm,
                                                v_disaster_reg_ymd,
                                                v_disaster_mdfcn_ymd))
            v_kafka_message = {'character_type_code':v_character_type_code,
                               'character_content':v_msg_cn,
                               'disaster_sn':v_disaster_sn,
                               'disaster_crt_dt':v_disaster_crt_dt.isoformat() if v_disaster_crt_dt else None,
                               'disaster_rcptn_rgn_nm':v_disaster_rcptn_rgn_nm,
                               'disaster_emrg_step_nm':v_disaster_emrg_step_nm,
                               'disaster_dst_se_nm':v_disaster_dst_se_nm,
                               'disaster_reg_ymd':v_disaster_reg_ymd.isoformat() if v_disaster_crt_dt else None,
                               'disaster_mdfcn_ymd':v_disaster_mdfcn_ymd.isoformat() if v_disaster_crt_dt else None}
            v_producer.send('Topic_characters',v_kafka_message)
            v_count += 1
   v_conn.close()
   return v_count
def f_exists(v_cursor,a_msg_cn):
   v_sql = "SELECT 1 FROM multicampus_schema.characters WHERE character_content = %s LIMIT 1"
   v_cursor.execute(v_sql,(a_msg_cn,))
   v_row = v_cursor.fetchone()
   return v_row is not None
def f_classify_type(a_emrg_step_nm):
   if a_emrg_step_nm is None:
      return 'NO'
   if '위급재난' in a_emrg_step_nm:
      return 'EX'
   if '긴급재난' in a_emrg_step_nm:
      return 'EM'
   if '안전안내' in a_emrg_step_nm:
      return 'SA'
   return 'NO'
def f_parse_timestamp(a_value):
   if a_value is None:
      return None
   v_value = str(a_value).strip()
   if v_value == '':
      return None
   if '.' in v_value:
      v_value = v_value.split('.')[0]
   return datetime.strptime(v_value,'%Y/%m/%d %H:%M:%S')
def f_strip_or_null(a_value):
   if a_value is None:
      return None
   v_value = str(a_value).strip()
   return v_value if v_value != '' else None
def f_get_kafka_producer():
   v_producer = KafkaProducer(bootstrap_servers='56.155.47.51:8908',value_serializer=lambda v_data:json.dumps(v_data,ensure_ascii=False).encode('UTF-8'))
   return v_producer
if __name__ == '__main__':
   f_main()