#!/bin/bash
set -e

HADOOP_HOME=${HADOOP_HOME:-/opt/hadoop}
HDFS="$HADOOP_HOME/bin/hdfs"

# 설정 파일 복사 (마운트된 conf → Hadoop 설정 디렉토리)
cp /etc/hadoop-conf/core-site.xml "$HADOOP_HOME/etc/hadoop/core-site.xml"
cp /etc/hadoop-conf/hdfs-site.xml "$HADOOP_HOME/etc/hadoop/hdfs-site.xml"

# 데이터 디렉토리 생성
mkdir -p /opt/hadoop/data/namenode /opt/hadoop/data/datanode

# NameNode 최초 포맷 (namenode 데이터가 없을 때만)
if [ ! -d /opt/hadoop/data/namenode/current ]; then
  echo ">>> NameNode 최초 포맷 중..."
  $HDFS namenode -format -force -nonInteractive
fi

# DataNode 백그라운드 시작
echo ">>> DataNode 시작..."
$HDFS --daemon start datanode

# /DFCS 디렉토리 생성 (WebHDFS가 올라올 때까지 대기 후)
(
  sleep 10
  echo ">>> HDFS /DFCS 디렉토리 초기화..."
  $HDFS dfs -mkdir -p /DFCS || true
  $HDFS dfs -chmod 777 /DFCS || true
  echo ">>> HDFS 준비 완료"
) &

# NameNode 포그라운드 실행 (컨테이너 메인 프로세스)
echo ">>> NameNode 시작..."
exec $HDFS namenode
