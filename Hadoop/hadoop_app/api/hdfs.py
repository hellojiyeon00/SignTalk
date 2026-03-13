from fastapi import APIRouter, Body

from hadoop_app.services.hdfs_service import f_save_hdfs, C_Hadoop

router = APIRouter()

@router.post("/save_hdfs")
async def save_hdfs(data: C_Hadoop):
    return await f_save_hdfs(data)