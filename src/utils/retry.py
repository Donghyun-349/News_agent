"""재시도 로직 유틸리티"""

import time
import logging
from typing import Callable, TypeVar, Optional, Any
from functools import wraps

T = TypeVar('T')
logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    재시도 로직이 포함된 데코레이터 (exponential backoff).
    
    Args:
        max_attempts: 최대 재시도 횟수
        initial_delay: 초기 대기 시간 (초)
        backoff_factor: 지연 시간 증가 배수
        exceptions: 재시도할 예외 타입들
    
    Returns:
        데코레이터 함수
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception: Optional[Exception] = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
            
            # 모든 재시도 실패
            if last_exception:
                raise last_exception
            
            # 이론적으로 도달 불가능하지만 타입 체커를 위해
            raise RuntimeError("Unexpected error in retry logic")
        
        return wrapper
    return decorator




















