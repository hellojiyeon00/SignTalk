from __future__ import annotations

import argparse
import socketio
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FastText log generator via Socket.IO chat messages")
    parser.add_argument(
        "--base_url",
        type=str,
        default="http://56.155.47.51:8951",
        help="Socket.IO 서버 주소",
    )
    parser.add_argument(
        "--sentences_path",
        type=str,
        required=True,
        help="테스트 문장 txt 파일 경로 (한 줄에 한 문장)",
    )
    parser.add_argument(
        "--room",
        type=str,
        default="hodol0213_soyoung92",
        help="채팅방 이름",
    )
    parser.add_argument(
        "--room_id",
        type=int,
        default=33,
        help="채팅방 ID",
    )
    parser.add_argument(
        "--username",
        type=str,
        required=True,
        help="보내는 사용자 ID",
    )
    parser.add_argument(
        "--access_token",
        type=str,
        required=True,
        help="JWT access token",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="메시지 간 전송 간격(초)",
    )
    return parser.parse_args()


def load_sentences(path: Path) -> list[str]:
    lines: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if text:
                lines.append(text)
    return lines


def main() -> None:
    args = parse_args()
    sentences = load_sentences(Path(args.sentences_path))

    if not sentences:
        raise ValueError("테스트 문장이 비어 있음")

    sio = socketio.Client(logger=True, engineio_logger=True)

    @sio.event
    def connect():
        print("socket connected")
        sio.emit("register_user", {"user_id": args.username})
        print(f"register_user sent: {args.username}")
        sio.emit("join_room", {"room": args.room, "username": args.username})
        print(f"join_room sent: room={args.room}")

    @sio.event
    def connect_error(data):
        print("connect_error:")
        print(data)

    @sio.event
    def disconnect():
        print("socket disconnected")

    @sio.on("receive_message")
    def on_receive_message(data):
        message = data.get("message")
        gloss = data.get("gloss")
        print(f"receive_message | message={message} | gloss={gloss}")

    try:
        sio.connect(
            args.base_url,
            auth={"token": args.access_token},
            transports=["websocket"],
            wait_timeout=10,
        )
    except Exception as e:
        print("sio.connect failed:", repr(e))
        raise

    time.sleep(1.0)

    for idx, msg in enumerate(sentences, start=1):
        payload = {
            "room": args.room,
            "room_id": args.room_id,
            "username": args.username,
            "message": msg,
        }
        sio.emit("send_message", payload)
        print(f"[{idx}/{len(sentences)}] {msg}")
        time.sleep(args.delay)

    time.sleep(3.0)
    sio.emit("leave_room", {"room": args.room, "username": args.username})
    sio.disconnect()


if __name__ == "__main__":
    main()
