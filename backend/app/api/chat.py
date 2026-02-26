"""채팅 관련 API 엔드포인트

친구 검색, 채팅방 생성/조회, 대화 내역 조회 기능 제공
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.api.schemas import RoomResponse, RoomCreateRequest, ReadMessagesRequest
from app.services.chat_service import ChatService
from app.api.auth import verify_token

router = APIRouter()

# @router.get("/search"): GET 요청으로 친구 검색 처리 (JWT 인증 필수)
@router.get("/search")
def search_user(
    name: Optional[str] = None,
    member_id: Optional[str] = None,
    current_user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """친구 검색 (이름 또는 아이디, JWT 토큰 필수)"""
    return ChatService.search_users(db, current_user_id, name, member_id)


# @router.post("/room"): POST 요청으로 채팅방 생성 또는 기존 방 조회 처리 (JWT 인증 필수)
@router.post("/room", response_model=RoomResponse)
def get_or_create_room(
    req: RoomCreateRequest,
    current_user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """채팅방 생성 또는 기존 방 조회 (JWT 토큰 필수)"""
    # 토큰의 user_id와 요청의 my_id가 일치하는지 확인
    from fastapi import HTTPException, status
    if req.my_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인만 채팅방을 생성할 수 있습니다."
        )
    return ChatService.create_or_get_room(db, current_user_id, req.target_id)


# @router.get("/list"): GET 요청으로 내 채팅방 목록 조회 처리 (JWT 인증 필수)
@router.get("/list")
def get_my_rooms(
    current_user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """내 채팅방 목록 조회 (JWT 토큰 필수)"""
    return ChatService.get_my_rooms(db, current_user_id)


# @router.get("/history/{room_id}"): GET 요청으로 특정 채팅방의 대화 내역 조회 처리 (JWT 인증 필수)
@router.get("/history/{room_id}")
def get_chat_history(
    room_id: int,
    current_user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """채팅방 대화 내역 조회 (읽음 상태 포함, JWT 토큰 필수)"""
    return ChatService.get_chat_history(db, room_id, current_user_id)


# @router.post("/friend/block"): POST 요청으로 친구 차단 처리 (JWT 인증 필수)
@router.post("/friend/block")
def block_friend(
    friend_id: str,
    current_user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """친구 차단 (소프트 차단, JWT 토큰 필수)"""
    return ChatService.block_friend(db, current_user_id, friend_id)


# @router.post("/friend/unblock"): POST 요청으로 친구 차단 해제 처리 (JWT 인증 필수)
@router.post("/friend/unblock")
def unblock_friend(
    friend_id: str,
    current_user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """친구 차단 해제 (JWT 토큰 필수)"""
    return ChatService.unblock_friend(db, current_user_id, friend_id)


# @router.post("/read"): POST 요청으로 메시지 읽음 처리 (JWT 인증 필수)
@router.post("/read")
def mark_messages_as_read(
    req: ReadMessagesRequest,
    current_user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """채팅방 메시지 읽음 처리 (JWT 토큰 필수)"""
    return ChatService.mark_messages_as_read(db, req.room_id, current_user_id)


# @router.get("/friends"): GET 요청으로 친구 목록 조회 처리 (JWT 인증 필수)
@router.get("/friends")
def get_friend_list(
    current_user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """친구 목록 조회 (JWT 토큰 필수)"""
    return ChatService.get_friend_list(db, current_user_id)