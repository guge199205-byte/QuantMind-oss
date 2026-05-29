"""Qlib 任务状态清洗工具"""

from typing import Any


def _sanitize_task_info(value: Any, depth: int = 0) -> Any:
    """将 Celery task info 转为可 JSON 序列化结构。"""
    if depth > 4:
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, BaseException):
        return {
            "error": str(value),
            "exception_type": type(value).__name__,
        }
    if isinstance(value, dict):
        return {str(k): _sanitize_task_info(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_task_info(v, depth + 1) for v in value]
    return str(value)
