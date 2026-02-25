"""
logging_config.py

model_server 공통 로깅 설정
- 콘솔 + 파일 동시 출력
- RotatingFileHandler로 파일 용량 제한 + 백업
- 모듈별 logger = logging.getLogger(__name__) 사용
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

def _resolve_log_dir(log_dir: str | None) -> str:
    """
    로그 디렉토리 결정

    우선순위:
    1) setup_logging 인자
    2) 환경변수 LOG_DIR
    3) 기본값: /home/lab06/logs/signtalk (프로젝트 외부)
    """
    base = (log_dir or os.getenv("LOG_DIR") or "/home/lab06/logs/signtalk").strip()
    path = os.path.abspath(base)
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def setup_logging(
        *,
        log_dir: str | None = None,
        log_file: str = "model_server.log",
        level: str | int = "INFO"
) -> None:
    """
    model_server 로깅을 초기화한다.
    
    Args:
        log_dir: 로그 디렉토리 경로(상대/절대 모두 가능)
        log_file: 로그 파일명
        level: 로깅 레벨 (예: "DEBUG", "INFO", "WARNING", "ERROR")
    """
    root = logging.getLogger()
    if getattr(root, "_model_server_logging_configured", False):
        return
    
    if isinstance(level, str):
        level_value = getattr(logging, level.upper(), logging.INFO)
    else:
        level_value = level

    root.setLevel(level_value)

    resolved_log_dir = _resolve_log_dir(log_dir)
    file_path = os.path.join(resolved_log_dir, log_file)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 콘솔
    sh = logging.StreamHandler()
    sh.setLevel(level_value)
    sh.setFormatter(formatter)

    # 파일 로데이션(5MB, 5개 백업)
    fh = RotatingFileHandler(
        file_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    fh.setLevel(level_value)
    fh.setFormatter(formatter)

    root.addHandler(sh)
    root.addHandler(fh)

    # 중복 설정 방지 플래그
    root._model_server_logging_configured = True

# log_dir를 넘기지 않으면 무조건 /home/lab06/logs/signtalk 사용
# LOG_DIR 환경변수가 있으면 그 값 우선
# 더 이상 프로젝트 내부 logs/ 생성/갱신 없음
