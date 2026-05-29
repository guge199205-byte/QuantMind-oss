"""通用工具模块"""

import asyncio
import functools
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar
from collections.abc import Callable

from fastapi import HTTPException, status
from pydantic import BaseModel

from .logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class APIResponse(BaseModel):
    """标准API响应模型"""

    success: bool = True
    message: str = "操作成功"
    data: Any | None = None
    timestamp: datetime = datetime.now(timezone.utc)


class ErrorResponse(BaseModel):
    """错误响应模型"""

    success: bool = False
    message: str
    error_code: str | None = None
    details: dict[str, Any] | None = None
    timestamp: datetime = datetime.now(timezone.utc)


def success_response(data: Any = None, message: str = "操作成功") -> APIResponse:
    """创建成功响应

    Args:
        data: 响应数据
        message: 响应消息

    Returns:
        标准API响应
    """
    return APIResponse(data=data, message=message)


def error_response(
    message: str,
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
) -> ErrorResponse:
    """创建错误响应

    Args:
        message: 错误消息
        error_code: 错误代码
        details: 错误详情

    Returns:
        错误响应
    """
    return ErrorResponse(message=message, error_code=error_code, details=details)


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """重试装饰器

    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 延迟倍数
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay} seconds..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}: {e}")

            raise last_exception

        return wrapper

    return decorator


def async_retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """异步重试装饰器

    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 延迟倍数
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay} seconds..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}: {e}")

            raise last_exception

        return wrapper

    return decorator


def timing(func: Callable[..., T]) -> Callable[..., T]:
    """性能计时装饰器

    Args:
        func: 要计时的函数

    Returns:
        装饰后的函数
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> T:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} executed in {execution_time:.4f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.4f} seconds: {e}")
            raise

    return wrapper


def validate_pagination(page: int = 1, size: int = 20, max_size: int = 100) -> tuple[int, int]:
    """验证分页参数

    Args:
        page: 页码
        size: 每页大小
        max_size: 最大每页大小

    Returns:
        验证后的页码和每页大小

    Raises:
        HTTPException: 参数无效时抛出
    """
    if page < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="页码必须大于0")

    if size < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="每页大小必须大于0")

    if size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"每页大小不能超过{max_size}",
        )

    return page, size


def calculate_offset(page: int, size: int) -> int:
    """计算数据库查询偏移量

    Args:
        page: 页码
        size: 每页大小

    Returns:
        偏移量
    """
    return (page - 1) * size


def format_currency(amount: float, currency: str = "CNY") -> str:
    """格式化货币金额

    Args:
        amount: 金额
        currency: 货币类型

    Returns:
        格式化后的货币字符串
    """
    if currency == "CNY":
        return f"¥{amount:,.2f}"
    elif currency == "USD":
        return f"${amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """安全除法，避免除零错误

    Args:
        numerator: 分子
        denominator: 分母
        default: 除零时的默认值

    Returns:
        除法结果或默认值
    """
    if denominator == 0:
        return default
    return numerator / denominator


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """截断字符串

    Args:
        text: 原始字符串
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的字符串
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def batch_process(items: list[T], batch_size: int = 100) -> list[list[T]]:
    """批量处理数据

    Args:
        items: 要处理的数据列表
        batch_size: 批次大小

    Returns:
        分批后的数据列表
    """
    batches = []
    for i in range(0, len(items), batch_size):
        batches.append(items[i : i + batch_size])
    return batches


def normalize_user_id(user_id: Any) -> str:
    """标准化 UserID 为 8 位数格式

    Args:
        user_id: 原始 UserID (字符串或数字)

    Returns:
        8 位补齐后的字符串。非数字格式保持原样或进行基本处理。
    """
    if user_id is None:
        return "00000000"
    uid_str = str(user_id).strip()
    if uid_str.isdigit():
        return uid_str.zfill(8)
    return uid_str
