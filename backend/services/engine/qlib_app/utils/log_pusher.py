"""
Redis 日志推送工具类

用于将遗传算法优化过程中的日志推送到 Redis，
供前端实时查询显示。
"""

import logging
import os
from datetime import datetime
from typing import Optional

import redis

from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

logger = logging.getLogger(__name__)


class RedisLogPusher:
    """Redis 日志推送器

    负责将日志消息推送到 Redis 列表，供前端实时查询。
    日志格式：带时间戳的文本消息
    Redis Key: qlib:logs:{optimization_id}
    过期时间: 7天
    """

    def __init__(self, optimization_id: str):
        """初始化日志推送器

        Args:
            optimization_id: 优化任务ID
        """
        self.optimization_id = optimization_id
        self.redis_client = self._init_redis()
        self.log_key = f"qlib:logs:{optimization_id}"
        self._log = StructuredTaskLogger(logger, "redis-log-pusher", {"optimization_id": optimization_id})

        if self.redis_client:
            self._log.info("init", "Redis日志推送器已初始化")
        else:
            self._log.warning("init_failed", "Redis连接失败，日志将不会推送到Redis")

    def _init_redis(self) -> redis.Redis | None:
        """初始化 Redis 连接

        Returns:
            Redis 客户端实例，失败时返回 None
        """
        try:
            REDIS_HOST = os.getenv("REDIS_HOST", "host.docker.internal")
            REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
            REDIS_DB = int(os.getenv("REDIS_DB", 0))

            client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )

            # 测试连接
            client.ping()
            return client

        except Exception as e:
            self._log.error("redis_connect_error", "Redis 连接失败", error=e)
            return None

    def push_log(self, message: str):
        """推送日志消息到 Redis

        Args:
            message: 日志消息内容
        """
        if not self.redis_client:
            # Redis 不可用时，仅记录到 Python logger
            return

        try:
            # 添加时间戳
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"

            # 推送到 Redis 列表
            self.redis_client.rpush(self.log_key, formatted_message)

            # 设置过期时间 (7天)
            self.redis_client.expire(self.log_key, 7 * 24 * 3600)

        except Exception as e:
            self._log.warning("push_failed", "日志推送失败", error=e)

    def push_logs(self, messages: list[str]):
        """批量推送日志消息

        Args:
            messages: 日志消息列表
        """
        for message in messages:
            self.push_log(message)

    def close(self):
        """关闭 Redis 连接"""
        if self.redis_client:
            try:
                self.redis_client.close()
                self._log.debug("close", "Redis日志推送器已关闭")
            except Exception as e:
                self._log.warning("close_failed", "关闭Redis连接失败", error=e)
