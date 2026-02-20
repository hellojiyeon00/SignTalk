"""FastAPI 메인 애플리케이션

Socket.IO를 지원하는 채팅 서버 설정
"""
import asyncio
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.disaster import router as disaster_router
from app.api.location import router as location_router
from app.api.sockets import sio
from app.services.disaster_service import DisasterService

# FastAPI 앱 생성
app = FastAPI(title="Chat API", version="1.0.0")

# CORS 설정 - 개발 환경용 (프로덕션에서는 특정 origin만 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(auth_router, prefix="/auth", tags=["인증"])
app.include_router(chat_router, prefix="/chat", tags=["채팅"])
app.include_router(disaster_router, prefix="/disaster", tags=["재난문자"])
app.include_router(location_router, prefix="/location", tags=["위치"])

# 서버 시작 시 실행할 초기화 작업 - Socket.IO 래핑 전에 등록!
@app.on_event("startup")
async def startup_event():
    # SSE 재난문자 리스너를 백그라운드에서 가동합니다.
    asyncio.create_task(DisasterService.start_disaster_listener())

# Socket.IO 통합 - FastAPI 앱을 Socket.IO ASGI 앱으로 래핑
app = socketio.ASGIApp(sio, app)
