#!/usr/bin/env python3
"""
WebSocket 消息队列
支持异步消息队列、背压控制和消息优先级
Created: 2025-11-12
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """消息优先级"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class QueuedMessage:
    """队列消息"""

    connection_id: str
    message: dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = 0.0
    retry_count: int = 0

    def __lt__(self, other):
        """比较优先级（用于优先队列）"""
        if self.priority != other.priority:
            return self.priority.value > other.priority.value
        return self.timestamp < other.timestamp


class MessageQueue:
    """
    WebSocket 消息队列

    功能:
    - 异步消息队列
    - 消息优先级
    - 背压控制
    - 批量发送
    - 重试机制
    """

    def __init__(
        self,
        max_size: int = 10000,
        max_backpressure_size: int = 5000,
        batch_size: int = 10,
        batch_timeout: float = 0.1,
    ):
        """
        初始化消息队列

        Args:
            max_size: 队列最大大小
            max_backpressure_size: 触发背压的阈值
            batch_size: 批量发送大小
            batch_timeout: 批量超时时间（秒）
        """
        self.max_size = max_size
        self.max_backpressure_size = max_backpressure_size
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout

        # 使用 asyncio.Queue
        self.queue: asyncio.Queue[QueuedMessage] = asyncio.Queue(maxsize=max_size)

        # 统计信息
        self.enqueued_count = 0
        self.dequeued_count = 0
        self.dropped_count = 0
        self.backpressure_count = 0

        logger.info(f"消息队列初始化: max_size={max_size}, batch_size={batch_size}")

    async def enqueue(
        self,
        connection_id: str,
        message: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> bool:
        """
        消息入队

        Args:
            connection_id: 连接ID
            message: 消息内容
            priority: 消息优先级

        Returns:
            是否成功入队
        """
        # 检查队列大小
        qsize = self.queue.qsize()

        # 背压控制
        if qsize >= self.max_backpressure_size:
            self.backpressure_count += 1

            # 如果是低优先级消息，直接丢弃
            if priority == MessagePriority.LOW:
                self.dropped_count += 1
                logger.warning(f"队列背压，丢弃低优先级消息: {connection_id}")
                return False

            # 高优先级消息等待一小段时间
            if priority in (MessagePriority.HIGH, MessagePriority.URGENT):
                try:
                    await asyncio.wait_for(self._wait_for_space(), timeout=1.0)
                except asyncio.TimeoutError:
                    self.dropped_count += 1
                    logger.warning(f"队列满，丢弃消息: {connection_id}")
                    return False

        # 创建队列消息
        queued_msg = QueuedMessage(
            connection_id=connection_id,
            message=message,
            priority=priority,
            timestamp=time.time(),
        )

        try:
            # 非阻塞入队
            self.queue.put_nowait(queued_msg)
            self.enqueued_count += 1
            return True

        except asyncio.QueueFull:
            self.dropped_count += 1
            logger.warning(f"队列已满，丢弃消息: {connection_id}")
            return False

    async def _wait_for_space(self):
        """等待队列有空间"""
        while self.queue.qsize() >= self.max_backpressure_size:
            await asyncio.sleep(0.01)

    async def dequeue(self) -> QueuedMessage | None:
        """
        消息出队

        Returns:
            队列消息，队列为空时返回None
        """
        try:
            msg = await asyncio.wait_for(self.queue.get(), timeout=self.batch_timeout)
            self.dequeued_count += 1
            return msg

        except asyncio.TimeoutError:
            return None

    async def dequeue_batch(self, max_size: int | None = None) -> list[QueuedMessage]:
        """
        批量出队

        Args:
            max_size: 最大批量大小，None则使用默认值

        Returns:
            消息列表
        """
        batch_size = max_size or self.batch_size
        messages = []

        # 获取第一个消息（阻塞）
        first_msg = await self.dequeue()
        if first_msg is None:
            return messages

        messages.append(first_msg)

        # 非阻塞获取更多消息
        for _ in range(batch_size - 1):
            try:
                msg = self.queue.get_nowait()
                messages.append(msg)
                self.dequeued_count += 1
            except asyncio.QueueEmpty:
                break

        return messages

    def qsize(self) -> int:
        """获取队列当前大小"""
        return self.queue.qsize()

    def is_empty(self) -> bool:
        """队列是否为空"""
        return self.queue.empty()

    def is_full(self) -> bool:
        """队列是否已满"""
        return self.queue.full()

    def is_backpressure(self) -> bool:
        """是否处于背压状态"""
        return self.queue.qsize() >= self.max_backpressure_size

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "queue_size": self.qsize(),
            "max_size": self.max_size,
            "backpressure_threshold": self.max_backpressure_size,
            "is_backpressure": self.is_backpressure(),
            "enqueued_total": self.enqueued_count,
            "dequeued_total": self.dequeued_count,
            "dropped_total": self.dropped_count,
            "backpressure_count": self.backpressure_count,
            "pending_messages": self.qsize(),
        }

    def clear(self):
        """清空队列"""
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        logger.info("消息队列已清空")


# 全局消息队列实例
message_queue = MessageQueue()
