"""로깅 설정 모듈"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "news_ingestor",
    log_level: str = "INFO",
    log_dir: str = "logs",
    console_output: bool = True
) -> logging.Logger:
    """
    로거를 설정하고 반환합니다.
    
    Args:
        name: 로거 이름
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: 로그 파일 저장 디렉토리
        console_output: 콘솔 출력 여부
    
    Returns:
        설정된 Logger 인스턴스
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # 기존 핸들러 제거 (중복 방지)
    logger.handlers.clear()
    
    # 로그 포맷 설정
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 콘솔 핸들러
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 파일 핸들러
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # 일별 로그 파일
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = log_path / f"app_{today}.log"
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    기존 로거를 가져오거나 새로 생성합니다.
    
    Args:
        name: 로거 이름 (None이면 루트 로거)
    
    Returns:
        Logger 인스턴스
    """
    if name:
        return logging.getLogger(name)
    return logging.getLogger()


# 기본 로거 인스턴스 (모듈 임포트 시 자동 설정)
_default_logger: Optional[logging.Logger] = None


def get_default_logger() -> logging.Logger:
    """기본 로거를 반환합니다 (지연 초기화)."""
    global _default_logger
    if _default_logger is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")
        _default_logger = setup_logger(log_level=log_level)
    return _default_logger




















