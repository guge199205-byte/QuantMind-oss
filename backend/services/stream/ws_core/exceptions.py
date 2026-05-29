#!/usr/bin/env python3
"""
WebSocket 异常处理
Created: 2025-11-12
"""

import logging
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """错误代码"""

    # 连接错误 (1xxx)
    CONNECTION_FAILED = 1001
    CONNECTION_TIMEOUT = 1002
    CONNECTION_CLOSED = 1003
    CONNECTION_LIMIT_EXCEEDED = 1004

    # 认证错误 (2xxx)
    AUTH_FAILED = 2001
    AUTH_TIMEOUT = 2002
    AUTH_REQUIRED = 2003
    INVALID_TOKEN = 2004

    # 消息错误 (3xxx)
    MESSAGE_TOO_LARGE = 3001
    MESSAGE_INVALID_FORMAT = 3002
    MESSAGE_RATE_LIMIT = 3003

    # 订阅错误 (4xxx)
    SUBSCRIPTION_FAILED = 4001
    SUBSCRIPTION_LIMIT_EXCEEDED = 4002
    INVALID_TOPIC = 4003

    # 数据错误 (5xxx)
    DATA_SOURCE_ERROR = 5001
    DATA_NOT_FOUND = 5002
    DATA_FORMAT_ERROR = 5003

    # 服务器错误 (9xxx)
    INTERNAL_ERROR = 9001
    SERVICE_UNAVAILABLE = 9002


class WebSocketError(Exception):
    """WebSocket 基础异常"""

    def __init__(self, code: ErrorCode, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "error": True,
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
        }

    def to_client_message(self) -> dict[str, Any]:
        """转换为客户端消息"""
        return {
            "type": "error",
            "error_code": self.code.value,
            "error_message": self.message,
            "timestamp": None,  # 由发送方填充
        }


class ConnectionError(WebSocketError):
    """连接错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(ErrorCode.CONNECTION_FAILED, message, details)


class AuthenticationError(WebSocketError):
    """认证错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(ErrorCode.AUTH_FAILED, message, details)


class MessageError(WebSocketError):
    """消息错误"""

    def __init__(self, code: ErrorCode, message: str, details: dict[str, Any] | None = None):
        super().__init__(code, message, details)


class SubscriptionError(WebSocketError):
    """订阅错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(ErrorCode.SUBSCRIPTION_FAILED, message, details)


class DataSourceError(WebSocketError):
    """数据源错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(ErrorCode.DATA_SOURCE_ERROR, message, details)


async def handle_websocket_error(
    connection_id: str, error: Exception, send_to_client: bool = True
) -> dict[str, Any] | None:
    """
    处理 WebSocket 错误

    Args:
        connection_id: 连接ID
        error: 异常对象
        send_to_client: 是否发送错误消息到客户端

    Returns:
        错误消息字典，如果不需要发送则返回None
    """
    # WebSocket 自定义错误
    if isinstance(error, WebSocketError):
        logger.warning(f"WebSocket错误 [{connection_id}]: " f"code={error.code.value}, msg={error.message}")

        if send_to_client:
            return error.to_client_message()
        return None

    # 其他异常
    logger.error(f"未处理的异常 [{connection_id}]: {type(error).__name__}: {error}")

    if send_to_client:
        return {
            "type": "error",
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "error_message": "Internal server error",
            "timestamp": None,
        }

    return None


def create_error_message(code: ErrorCode, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    创建错误消息

    Args:
        code: 错误代码
        message: 错误消息
        details: 详细信息

    Returns:
        错误消息字典
    """
    import time

    return {
        "type": "error",
        "error_code": code.value,
        "error_message": message,
        "details": details or {},
        "timestamp": time.time(),
    }
