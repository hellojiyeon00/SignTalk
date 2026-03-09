from fastapi import APIRouter, Body

from model_app.services.lstm_service import transfer_sign2gloss

router = APIRouter()

@router.post("/sign2text")
async def sign2text(data: dict = Body(...)):
    return await transfer_sign2gloss(data)