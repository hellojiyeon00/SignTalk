"""채팅 관련 API 엔드포인트

친구 검색, 채팅방 생성/조회, 대화 내역 조회 기능 제공
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.api.schemas import RoomResponse, RoomCreateRequest
from app.services.chat_service import ChatService

router = APIRouter()

# @router.get("/search"): GET 요청으로 친구 검색 처리
@router.get("/search")
def search_user(
    my_id: str,
    name: Optional[str] = None,
    member_id: Optional[str] = None,
    # DB 세션 의존성 주입
    db: Session = Depends(get_db)
):
    """친구 검색 (이름 또는 아이디)"""
    return ChatService.search_users(db, my_id, name, member_id)


# @router.post("/room"): POST 요청으로 채팅방 생성 또는 기존 방 조회 처리
@router.post("/room", response_model=RoomResponse)
def get_or_create_room(req: RoomCreateRequest, db: Session = Depends(get_db)):
    """채팅방 생성 또는 기존 방 조회"""
    return ChatService.create_or_get_room(db, req.my_id, req.target_id)


# @router.get("/list"): GET 요청으로 내 채팅방 목록 조회 처리
@router.get("/list")
def get_my_rooms(user_id: str, db: Session = Depends(get_db)):
    """내 채팅방 목록 조회"""
    return ChatService.get_my_rooms(db, user_id)


# @router.get("/history/{room_id}"): GET 요청으로 특정 채팅방의 대화 내역 조회 처리
@router.get("/history/{room_id}")
def get_chat_history(room_id: int, user_id: str, db: Session = Depends(get_db)):
    """채팅방 대화 내역 조회 (읽음 상태 포함)"""
    return ChatService.get_chat_history(db, room_id, user_id)


# @router.post("/friend/block"): POST 요청으로 친구 차단 처리
@router.post("/friend/block")
def block_friend(
    my_id: str,
    friend_id: str,
    db: Session = Depends(get_db)
):
    """친구 차단 (소프트 차단)"""
    return ChatService.block_friend(db, my_id, friend_id)


# @router.post("/friend/unblock"): POST 요청으로 친구 차단 해제 처리
@router.post("/friend/unblock")
def unblock_friend(
    my_id: str,
    friend_id: str,
    db: Session = Depends(get_db)
):
    """친구 차단 해제"""
    return ChatService.unblock_friend(db, my_id, friend_id)


# @router.post("/read"): POST 요청으로 메시지 읽음 처리
@router.post("/read")
def mark_messages_as_read(
    room_id: int,
    user_id: str,
    db: Session = Depends(get_db)
):
    """채팅방 메시지 읽음 처리"""
    return ChatService.mark_messages_as_read(db, room_id, user_id)


# @router.get("/friends"): GET 요청으로 친구 목록 조회 처리
@router.get("/friends")
def get_friend_list(
    user_id: str,
    db: Session = Depends(get_db)
):
    """친구 목록 조회"""
    return ChatService.get_friend_list(db, user_id)