"""FastAPI 메인 애플리케이션

Socket.IO를 지원하는 채팅 서버 설정
"""
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.sockets import sio

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

# Socket.IO 통합 - FastAPI 앱을 Socket.IO ASGI 앱으로 래핑
app = socketio.ASGIApp(sio, app)

