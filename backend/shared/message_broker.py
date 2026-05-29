#!/usr/bin/env python3
"""
消息代理模块
提供消息队列、发布订阅、事件驱动等功能
"""

import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
from collections.abc import Callable
from uuid import uuid4

from .service_communication import ServiceMessage

logger = logging.getLogger(__name__)


class ExchangeType(str, Enum):
    """交换机类型"""

    DIRECT = "direct"
    TOPIC = "topic"
    FANOUT = "fanout"
    HEADERS = "headers"


class QueueType(str, Enum):
    """队列类型"""

    MEMORY = "memory"
    REDIS = "redis"
    RABBITMQ = "rabbitmq"
    KAFKA = "kafka"


@dataclass
class QueueConfig:
    """队列配置"""

    name: str
    exchange: str = "default"
    routing_key: str = ""
    exchange_type: ExchangeType = ExchangeType.DIRECT
    queue_type: QueueType = QueueType.MEMORY
    max_size: int = 10000
    ttl: int = 3600  # 秒
    durable: bool = False
    auto_delete: bool = True


@dataclass
class Subscription:
    """订阅信息"""

    id: str
    queue: str
    pattern: str
    callback: Callable
    auto_ack: bool = True
    exclusive: bool = False


class MessageQueue(ABC):
    """消息队列抽象基类"""

    @abstractmethod
    async def publish(self, message: ServiceMessage, routing_key: str = "") -> bool:
        """发布消息"""

    @abstractmethod
    async def consume(self, queue: str, callback: Callable) -> None:
        """消费消息"""

    @abstractmethod
    async def create_queue(self, config: QueueConfig) -> bool:
        """创建队列"""

    @abstractmethod
    async def delete_queue(self, queue_name: str) -> bool:
        """删除队列"""

    @abstractmethod
    async def get_queue_size(self, queue_name: str) -> int:
        """获取队列大小"""


class MemoryMessageQueue(MessageQueue):
    """内存消息队列"""

    def __init__(self):
        self._queues: dict[str, deque] = defaultdict(deque)
        self._queues_config: dict[str, QueueConfig] = {}
        self._subscribers: dict[str, list[Subscription]] = defaultdict(list)
        self._consumers: dict[str, list[Callable]] = defaultdict(list)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def publish(self, message: ServiceMessage, routing_key: str = "") -> bool:
        """发布消息"""
        try:
            # 根据路由键找到目标队列
            target_queues = self._find_target_queues(message.target_service, routing_key)

            if not target_queues:
                logger.warning(f"没有找到目标队列: {message.target_service}, {routing_key}")
                return False

            # 发布到所有目标队列
            success_count = 0
            for queue_name in target_queues:
                async with self._locks[queue_name]:
                    queue = self._queues[queue_name]
                    config = self._queues_config.get(queue_name)

                    # 检查队列大小限制
                    if config and len(queue) >= config.max_size:
                        logger.warning(f"队列 {queue_name} 已满，丢弃消息")
                        continue

                    # 检查TTL
                    if config and message.expires_at and time.time() > message.expires_at:
                        logger.debug(f"消息已过期，丢弃: {message.message_id}")
                        continue

                    queue.append(message)
                    success_count += 1

                    logger.debug(f"消息已发布到队列 {queue_name}: {message.message_id}")

            # 触发消费者
            for queue_name in target_queues:
                await self._trigger_consumers(queue_name)

            return success_count > 0

        except Exception as e:
            logger.error(f"发布消息失败: {e}")
            return False

    async def consume(self, queue: str, callback: Callable) -> None:
        """消费消息"""
        self._consumers[queue].append(callback)
        logger.info(f"注册消费者到队列: {queue}")

    async def create_queue(self, config: QueueConfig) -> bool:
        """创建队列"""
        try:
            self._queues_config[config.name] = config
            if config.name not in self._queues:
                self._queues[config.name] = deque(maxlen=config.max_size)
            logger.info(f"创建队列: {config.name}")
            return True
        except Exception as e:
            logger.error(f"创建队列失败: {e}")
            return False

    async def delete_queue(self, queue_name: str) -> bool:
        """删除队列"""
        try:
            if queue_name in self._queues:
                del self._queues[queue_name]
            if queue_name in self._queues_config:
                del self._queues_config[queue_name]
            if queue_name in self._consumers:
                del self._consumers[queue_name]
            if queue_name in self._subscribers:
                del self._subscribers[queue_name]
            if queue_name in self._locks:
                del self._locks[queue_name]

            logger.info(f"删除队列: {queue_name}")
            return True
        except Exception as e:
            logger.error(f"删除队列失败: {e}")
            return False

    async def get_queue_size(self, queue_name: str) -> int:
        """获取队列大小"""
        return len(self._queues.get(queue_name, []))

    def _find_target_queues(self, target_service: str, routing_key: str) -> list[str]:
        """根据目标服务和路由键找到目标队列"""
        target_queues = []

        # 直接匹配队列名
        direct_queue = f"{target_service}.{routing_key}"
        if direct_queue in self._queues:
            target_queues.append(direct_queue)

        # 服务队列
        service_queue = target_service
        if service_queue in self._queues:
            target_queues.append(service_queue)

        # 通用队列
        if "default" in self._queues:
            target_queues.append("default")

        return target_queues

    async def _trigger_consumers(self, queue_name: str):
        """触发消费者"""
        if not self._queues[queue_name]:
            return

        async with self._locks[queue_name]:
            if not self._queues[queue_name]:
                return

            message = self._queues[queue_name].popleft()

        # 调用所有消费者
        for consumer in self._consumers[queue_name]:
            try:
                await consumer(message)
            except Exception as e:
                logger.error(f"消费者处理消息失败: {e}")

    def get_queue_stats(self) -> dict[str, Any]:
        """获取队列统计"""
        stats = {"total_queues": len(self._queues), "queues": {}}

        for queue_name, queue in self._queues.items():
            config = self._queues_config.get(queue_name)
            stats["queues"][queue_name] = {
                "size": len(queue),
                "max_size": config.max_size if config else "unlimited",
                "consumers": len(self._consumers[queue_name]),
                "subscribers": len(self._subscribers[queue_name]),
            }

        return stats


class RedisMessageQueue(MessageQueue):
    """Redis消息队列"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._redis_client = None  # 这里应该初始化Redis客户端

    async def publish(self, message: ServiceMessage, routing_key: str = "") -> bool:
        """发布消息到Redis"""
        # 这里实现Redis发布逻辑
        # 暂时返回成功
        return True

    async def consume(self, queue: str, callback: Callable) -> None:
        """从Redis消费消息"""
        # 这里实现Redis消费逻辑

    async def create_queue(self, config: QueueConfig) -> bool:
        """在Redis中创建队列"""
        # 这里实现Redis队列创建逻辑
        return True

    async def delete_queue(self, queue_name: str) -> bool:
        """删除Redis队列"""
        # 这里实现Redis队列删除逻辑
        return True

    async def get_queue_size(self, queue_name: str) -> int:
        """获取Redis队列大小"""
        # 这里实现Redis队列大小查询逻辑
        return 0


class MessageBroker:
    """消息代理"""

    def __init__(self, queue_type: QueueType = QueueType.MEMORY, **kwargs):
        self.queue_type = queue_type
        self._queue = self._create_queue(queue_type, **kwargs)
        self._subscriptions: dict[str, Subscription] = {}
        self._event_handlers: dict[str, list[Callable]] = defaultdict(list)
        self._running = False

    def _create_queue(self, queue_type: QueueType, **kwargs) -> MessageQueue:
        """创建消息队列"""
        if queue_type == QueueType.MEMORY:
            return MemoryMessageQueue()
        elif queue_type == QueueType.REDIS:
            redis_url = kwargs.get("redis_url", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
            return RedisMessageQueue(redis_url)
        else:
            raise ValueError(f"Unsupported queue type: {queue_type}")

    async def start(self):
        """启动消息代理"""
        if self._running:
            return

        self._running = True
        logger.info(f"消息代理已启动，队列类型: {self.queue_type}")

    async def stop(self):
        """停止消息代理"""
        self._running = False
        logger.info("消息代理已停止")

    async def publish(self, message: ServiceMessage, routing_key: str = "", exchange: str = "default") -> bool:
        """发布消息"""
        if not self._running:
            logger.warning("消息代理未运行")
            return False

        try:
            success = await self._queue.publish(message, routing_key)

            # 触发事件处理器
            await self._trigger_event_handlers(
                "message.published",
                {
                    "message": message,
                    "routing_key": routing_key,
                    "exchange": exchange,
                    "success": success,
                },
            )

            return success

        except Exception as e:
            logger.error(f"发布消息失败: {e}")
            await self._trigger_event_handlers("message.publish_error", {"message": message, "error": str(e)})
            return False

    async def subscribe(
        self,
        pattern: str,
        callback: Callable,
        queue: str | None = None,
        auto_ack: bool = True,
        exclusive: bool = False,
    ) -> str:
        """订阅消息"""
        subscription_id = str(uuid4())
        queue_name = queue or f"subscription_{subscription_id}"

        # 创建订阅
        subscription = Subscription(
            id=subscription_id,
            queue=queue_name,
            pattern=pattern,
            callback=callback,
            auto_ack=auto_ack,
            exclusive=exclusive,
        )

        self._subscriptions[subscription_id] = subscription

        # 创建队列
        queue_config = QueueConfig(name=queue_name, exchange="default", routing_key=pattern, auto_delete=True)
        await self._queue.create_queue(queue_config)

        # 注册消费者
        await self._queue.consume(queue_name, self._create_message_handler(subscription))

        logger.info(f"订阅已创建: {subscription_id}, 模式: {pattern}")
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅"""
        if subscription_id not in self._subscriptions:
            return False

        subscription = self._subscriptions[subscription_id]

        # 删除队列
        await self._queue.delete_queue(subscription.queue)

        # 移除订阅
        del self._subscriptions[subscription_id]

        logger.info(f"订阅已取消: {subscription_id}")
        return True

    def _create_message_handler(self, subscription: Subscription) -> Callable:
        """创建消息处理器"""

        async def handler(message: ServiceMessage):
            try:
                # 检查消息是否匹配订阅模式
                if self._match_pattern(message.message_type, subscription.pattern):
                    await subscription.callback(message)

            except Exception as e:
                logger.error(f"消息处理失败: {e}")

        return handler

    def _match_pattern(self, message_type: str, pattern: str) -> bool:
        """匹配消息模式"""
        # 简单的通配符匹配
        if pattern == "*":
            return True
        elif pattern.endswith("*"):
            prefix = pattern[:-1]
            return message_type.startswith(prefix)
        elif pattern.startswith("*"):
            suffix = pattern[1:]
            return message_type.endswith(suffix)
        else:
            return message_type == pattern

    async def register_event_handler(self, event: str, handler: Callable):
        """注册事件处理器"""
        self._event_handlers[event].append(handler)
        logger.info(f"注册事件处理器: {event}")

    async def unregister_event_handler(self, event: str, handler: Callable):
        """取消注册事件处理器"""
        if handler in self._event_handlers[event]:
            self._event_handlers[event].remove(handler)
            logger.info(f"取消注册事件处理器: {event}")

    async def _trigger_event_handlers(self, event: str, data: dict[str, Any]):
        """触发事件处理器"""
        for handler in self._event_handlers[event]:
            try:
                await handler(data)
            except Exception as e:
                logger.error(f"事件处理器执行失败: {e}")

    async def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        queue_stats = {}
        if hasattr(self._queue, "get_queue_stats"):
            queue_stats = self._queue.get_queue_stats()

        return {
            "broker_type": self.queue_type,
            "running": self._running,
            "subscriptions": len(self._subscriptions),
            "event_handlers": {event: len(handlers) for event, handlers in self._event_handlers.items()},
            "queue_stats": queue_stats,
        }

    async def health_check(self) -> dict[str, Any]:
        """健康检查"""
        return {
            "status": "healthy" if self._running else "stopped",
            "queue_type": self.queue_type,
            "subscriptions": len(self._subscriptions),
            "timestamp": time.time(),
        }


# 全局消息代理实例
_message_broker: MessageBroker | None = None


def get_message_broker(queue_type: QueueType = QueueType.MEMORY, **kwargs) -> MessageBroker:
    """获取全局消息代理实例"""
    global _message_broker
    if _message_broker is None:
        _message_broker = MessageBroker(queue_type, **kwargs)
    return _message_broker


async def start_message_broker(queue_type: QueueType = QueueType.MEMORY, **kwargs):
    """启动消息代理"""
    broker = get_message_broker(queue_type, **kwargs)
    await broker.start()
    return broker


async def stop_message_broker():
    """停止消息代理"""
    global _message_broker
    if _message_broker:
        await _message_broker.stop()
        _message_broker = None


# 标准交换机和队列定义
class StandardExchanges:
    """标准交换机"""

    DEFAULT = "default"
    EVENTS = "events"
    ERRORS = "errors"
    METRICS = "metrics"
    HEALTH_CHECKS = "health_checks"


class StandardQueues:
    """标准队列"""

    # 服务队列
    USER_SERVICE = "user.service"
    AI_STRATEGY_SERVICE = "ai.strategy.service"
    MARKET_DATA_SERVICE = "market.data.service"
    BACKTEST_SERVICE = "backtest.service"
    TRADING_SERVICE = "trading.service"

    # 事件队列
    USER_EVENTS = "user.events"
    STRATEGY_EVENTS = "strategy.events"
    MARKET_EVENTS = "market.events"
    SYSTEM_EVENTS = "system.events"

    # 错误队列
    ERROR_QUEUE = "errors.default"
    DEAD_LETTER_QUEUE = "dead_letter.default"

    # 监控队列
    METRICS_QUEUE = "metrics.default"
    HEALTH_CHECK_QUEUE = "health_checks.default"


def create_standard_queues(broker: MessageBroker):
    """创建标准队列"""
    standard_queues = [
        QueueConfig(
            name=StandardQueues.USER_SERVICE,
            exchange=StandardExchanges.DEFAULT,
            durable=True,
        ),
        QueueConfig(
            name=StandardQueues.AI_STRATEGY_SERVICE,
            exchange=StandardExchanges.DEFAULT,
            durable=True,
        ),
        QueueConfig(
            name=StandardQueues.MARKET_DATA_SERVICE,
            exchange=StandardExchanges.DEFAULT,
            durable=True,
        ),
        QueueConfig(
            name=StandardQueues.BACKTEST_SERVICE,
            exchange=StandardExchanges.DEFAULT,
            durable=True,
        ),
        QueueConfig(
            name=StandardQueues.ERROR_QUEUE,
            exchange=StandardExchanges.ERRORS,
            durable=True,
        ),
        QueueConfig(
            name=StandardQueues.METRICS_QUEUE,
            exchange=StandardExchanges.METRICS,
            durable=True,
        ),
    ]

    for queue_config in standard_queues:
        asyncio.create_task(broker._queue.create_queue(queue_config))

    logger.info(f"创建了 {len(standard_queues)} 个标准队列")
