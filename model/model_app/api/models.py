from fastapi import APIRouter, Body

from model_app.services.lstm_service import transfer_sign2gloss

router = APIRouter()

@router.post("/sign2text")
async def sign2text(data: dict = Body(...)):
    return await transfer_sign2gloss(data)

@router.post("/text2sign")
async def text2gloss(data: dict = Body(...)):
    # 수신 확인
    return {"ok": True}