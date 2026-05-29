#!/usr/bin/env python3
"""
WebSocket连接管理器
Week 20 Day 3
Updated: 2025-11-12 - 集成消息队列
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

from .message_queue import MessagePriority, message_queue

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器

    管理所有WebSocket连接,包括:
    - 连接的建立和断开
    - 消息的发送和广播
    - 订阅管理
    - 心跳检测
    """

    def __init__(self):
        """初始化连接管理器"""
        # 活跃连接: {connection_id: WebSocket}
        self.active_connections: dict[str, WebSocket] = {}

        # 连接元数据: {connection_id: metadata}
        self.connection_metadata: dict[str, dict[str, Any]] = {}

        # 订阅管理: {topic: set(connection_ids)}
        self.subscriptions: dict[str, set[str]] = {}

        # 心跳时间戳: {connection_id: last_heartbeat_time}
        self.heartbeats: dict[str, float] = {}

        # 消息队列处理任务
        self.queue_processor_task: asyncio.Task | None = None
        self.processor_running = False

        logger.info("连接管理器初始化完成")

    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        建立连接

        Args:
            websocket: WebSocket连接对象
            connection_id: 连接唯一ID
            metadata: 连接元数据(用户信息等)

        Returns:
            是否成功建立连接
        """
        try:
            await websocket.accept()

            self.active_connections[connection_id] = websocket
            self.connection_metadata[connection_id] = metadata or {}
            self.heartbeats[connection_id] = time.time()

            logger.info(f"客户端连接成功: {connection_id}")
            logger.info(f"当前活跃连接数: {len(self.active_connections)}")

            return True

        except Exception as e:
            logger.error(f"连接失败 {connection_id}: {e}")
            return False

    async def disconnect(self, connection_id: str) -> None:
        """
        断开连接

        Args:
            connection_id: 连接ID
        """
        # 移除活跃连接
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        # 移除元数据
        if connection_id in self.connection_metadata:
            del self.connection_metadata[connection_id]

        # 移除心跳记录
        if connection_id in self.heartbeats:
            del self.heartbeats[connection_id]

        # 移除所有订阅
        for topic in list(self.subscriptions.keys()):
            if connection_id in self.subscriptions[topic]:
                self.subscriptions[topic].remove(connection_id)
                if not self.subscriptions[topic]:
                    del self.subscriptions[topic]

        logger.info(f"客户端断开连接: {connection_id}")
        logger.info(f"当前活跃连接数: {len(self.active_connections)}")

    async def close_connection(self, connection_id: str, code: int = 1000, reason: str = "") -> None:
        websocket = self.active_connections.get(connection_id)
        if websocket is not None:
            try:
                await websocket.close(code=code, reason=reason)
            except Exception as exc:
                logger.debug("关闭连接失败 %s: %s", connection_id, exc)
        await self.disconnect(connection_id)

    async def disconnect_all(self) -> None:
        """断开所有连接"""
        connection_ids = list(self.active_connections.keys())
        for connection_id in connection_ids:
            await self.disconnect(connection_id)
        logger.info("所有连接已断开")

    async def send_message(
        self,
        connection_id: str,
        message: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        use_queue: bool = True,
    ) -> bool:
        """
        发送消息给指定连接

        Args:
            connection_id: 连接ID
            message: 消息内容(字典)
            priority: 消息优先级
            use_queue: 是否使用消息队列

        Returns:
            是否发送成功
        """
        if connection_id not in self.active_connections:
            logger.warning(f"连接不存在: {connection_id}")
            return False

        # 使用消息队列（推荐）
        if use_queue:
            return await message_queue.enqueue(connection_id, message, priority)

        # 直接发送（用于紧急消息）
        try:
            websocket = self.active_connections[connection_id]
            await websocket.send_json(message)
            return True

        except Exception as e:
            logger.error(f"发送消息失败 {connection_id}: {e}")
            await self.disconnect(connection_id)
            return False

    async def broadcast(self, message: dict[str, Any], exclude: set[str] | None = None) -> int:
        """
        广播消息给所有连接

        Args:
            message: 消息内容
            exclude: 排除的连接ID集合

        Returns:
            成功发送的数量
        """
        exclude = exclude or set()
        success_count = 0

        for connection_id in list(self.active_connections.keys()):
            if connection_id not in exclude:
                if await self.send_message(connection_id, message):
                    success_count += 1

        return success_count

    async def subscribe(self, connection_id: str, topic: str) -> bool:
        """
        订阅主题

        Args:
            connection_id: 连接ID
            topic: 主题名称

        Returns:
            是否订阅成功
        """
        if connection_id not in self.active_connections:
            logger.warning(f"连接不存在: {connection_id}")
            return False

        if topic not in self.subscriptions:
            self.subscriptions[topic] = set()

        self.subscriptions[topic].add(connection_id)
        logger.info(f"客户端 {connection_id} 订阅主题: {topic}")

        return True

    async def unsubscribe(self, connection_id: str, topic: str) -> bool:
        """
        取消订阅主题

        Args:
            connection_id: 连接ID
            topic: 主题名称

        Returns:
            是否取消成功
        """
        if topic not in self.subscriptions:
            return False

        if connection_id in self.subscriptions[topic]:
            self.subscriptions[topic].remove(connection_id)
            logger.info(f"客户端 {connection_id} 取消订阅主题: {topic}")

            # 如果主题没有订阅者,删除主题
            if not self.subscriptions[topic]:
                del self.subscriptions[topic]

            return True

        return False

    async def publish(self, topic: str, message: dict[str, Any]) -> int:
        """
        向主题发布消息

        Args:
            topic: 主题名称
            message: 消息内容

        Returns:
            成功发送的数量
        """
        if topic not in self.subscriptions:
            return 0

        success_count = 0
        subscribers = list(self.subscriptions[topic])

        for connection_id in subscribers:
            if await self.send_message(connection_id, message):
                success_count += 1

        return success_count

    async def update_heartbeat(self, connection_id: str) -> None:
        """
        更新心跳时间

        Args:
            connection_id: 连接ID
        """
        if connection_id in self.heartbeats:
            self.heartbeats[connection_id] = time.time()

    def get_inactive_connections(self, timeout: int = 90) -> set[str]:
        """
        获取不活跃的连接

        Args:
            timeout: 超时时间(秒)

        Returns:
            不活跃的连接ID集合
        """
        current_time = time.time()
        inactive = set()

        for connection_id, last_time in self.heartbeats.items():
            if current_time - last_time > timeout:
                inactive.add(connection_id)

        return inactive

    async def check_connections(self, timeout: int = 90) -> None:
        """
        检查并清理不活跃的连接

        Args:
            timeout: 超时时间(秒)
        """
        inactive = self.get_inactive_connections(timeout)

        for connection_id in inactive:
            logger.warning(f"连接超时，断开: {connection_id}")
            await self.disconnect(connection_id)

    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        return {
            "active_connections": len(self.active_connections),
            "total_topics": len(self.subscriptions),
            "subscriptions": {topic: len(subscribers) for topic, subscribers in self.subscriptions.items()},
            "queue_stats": message_queue.get_stats(),
        }

    async def start_queue_processor(self):
        """启动消息队列处理器"""
        if self.processor_running:
            logger.warning("队列处理器已在运行")
            return

        self.processor_running = True
        self.queue_processor_task = asyncio.create_task(self._process_message_queue())
        logger.info("消息队列处理器已启动")

    async def stop_queue_processor(self):
        """停止消息队列处理器"""
        self.processor_running = False

        if self.queue_processor_task:
            self.queue_processor_task.cancel()
            try:
                await self.queue_processor_task
            except asyncio.CancelledError:
                pass

        logger.info("消息队列处理器已停止")

    async def _process_message_queue(self):
        """处理消息队列"""
        logger.info("开始处理消息队列")

        while self.processor_running:
            try:
                # 批量获取消息
                messages = await message_queue.dequeue_batch()

                if not messages:
                    continue

                # 批量发送消息
                for queued_msg in messages:
                    connection_id = queued_msg.connection_id
                    message = queued_msg.message

                    # 检查连接是否存在
                    if connection_id not in self.active_connections:
                        continue

                    # 发送消息
                    try:
                        websocket = self.active_connections[connection_id]
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.error(f"发送队列消息失败 {connection_id}: {e}")
                        # 重试逻辑
                        if queued_msg.retry_count < 3:
                            queued_msg.retry_count += 1
                            await message_queue.enqueue(connection_id, message, queued_msg.priority)
                        else:
                            # 超过重试次数，断开连接
                            await self.disconnect(connection_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"处理消息队列错误: {e}")
                await asyncio.sleep(0.1)


# 全局连接管理器实例
manager = ConnectionManager()
