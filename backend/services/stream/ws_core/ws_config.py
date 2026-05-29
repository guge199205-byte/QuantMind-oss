#!/usr/bin/env python3
"""
WebSocket配置
Week 20 Day 3
"""

import os

from pydantic import BaseModel


class WebSocketConfig(BaseModel):
    """WebSocket配置"""

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8014
    max_connections: int = 100

    # 心跳配置
    heartbeat_interval: int = 30  # 秒
    heartbeat_timeout: int = 90  # 秒

    # 消息配置
    max_message_size: int = 1024 * 1024  # 1MB
    message_queue_size: int = 100

    # 认证配置
    auth_required: bool = os.getenv("WS_AUTH_REQUIRED", "true").lower() == "true"
    auth_timeout: int = 10  # 秒

    # 重连配置
    reconnect_enabled: bool = True
    max_reconnect_attempts: int = 3
    reconnect_delay: int = 5  # 秒

    # 日志配置
    log_level: str = "INFO"
    log_connections: bool = True
    log_messages: bool = False


# 全局配置实例
ws_config = WebSocketConfig()
