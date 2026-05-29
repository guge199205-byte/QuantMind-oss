"""批量处理器.

提供批量操作、请求合并和并发控制功能.

Author: QuantMind Team
Date: 2025-11-05
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from collections.abc import Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class BatchRequest(Generic[T]):
    """批量请求."""

    request_id: str
    data: T
    created_at: datetime = field(default_factory=datetime.now)
    result: Any | None = None
    error: Exception | None = None
    completed: bool = False


class BatchProcessor(Generic[T, R]):
    """批量处理器.

    合并多个请求，批量处理以提高效率.
    """

    def __init__(
        self,
        batch_size: int = 10,
        max_wait_time: float = 0.1,
        processor: Callable[[list[T]], list[R]] | None = None,
    ):
        """初始化批量处理器.

        Args:
            batch_size: 批量大小
            max_wait_time: 最大等待时间（秒）
            processor: 批量处理函数
        """
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.processor = processor

        # 待处理队列
        self._queue: list[BatchRequest[T]] = []
        self._lock = asyncio.Lock()
        self._processing = False

        # 统计信息
        self._stats = {
            "total_requests": 0,
            "batches_processed": 0,
            "total_items": 0,
            "errors": 0,
        }

        logger.info(f"批量处理器初始化: batch_size={batch_size}, max_wait={max_wait_time}s")

    async def submit(self, data: T, request_id: str | None = None) -> R:
        """提交请求.

        Args:
            data: 请求数据
            request_id: 请求ID（可选）

        Returns:
            处理结果
        """
        if request_id is None:
            request_id = f"req_{self._stats['total_requests']}"

        request = BatchRequest(request_id=request_id, data=data)

        async with self._lock:
            self._queue.append(request)
            self._stats["total_requests"] += 1

        # 触发处理
        await self._trigger_processing()

        # 等待结果
        return await self._wait_for_result(request)

    async def _trigger_processing(self):
        """触发批量处理."""
        async with self._lock:
            if self._processing:
                return

            # 检查是否需要立即处理
            if len(self._queue) >= self.batch_size:
                self._processing = True
                asyncio.create_task(self._process_batch())
            else:
                # 等待更多请求或超时
                asyncio.create_task(self._wait_and_process())

    async def _wait_and_process(self):
        """等待并处理."""
        await asyncio.sleep(self.max_wait_time)

        async with self._lock:
            if not self._processing and self._queue:
                self._processing = True
                asyncio.create_task(self._process_batch())

    async def _process_batch(self):
        """处理一批请求."""
        try:
            async with self._lock:
                if not self._queue:
                    self._processing = False
                    return

                # 取出一批
                batch = self._queue[: self.batch_size]
                self._queue = self._queue[self.batch_size :]

            # 批量处理
            batch_data = [req.data for req in batch]

            try:
                if asyncio.iscoroutinefunction(self.processor):
                    results = await self.processor(batch_data)
                else:
                    results = self.processor(batch_data)

                # 设置结果
                for i, request in enumerate(batch):
                    request.result = results[i] if i < len(results) else None
                    request.completed = True

                self._stats["batches_processed"] += 1
                self._stats["total_items"] += len(batch)

                logger.debug(f"批量处理完成: {len(batch)}个请求")

            except Exception as e:
                # 所有请求都失败
                for request in batch:
                    request.error = e
                    request.completed = True

                self._stats["errors"] += len(batch)
                logger.error(f"批量处理失败: {e}")

        finally:
            async with self._lock:
                self._processing = False

                # 如果还有待处理的，继续
                if self._queue:
                    asyncio.create_task(self._process_batch())

    async def _wait_for_result(self, request: BatchRequest[T]) -> R:
        """等待请求结果.

        Args:
            request: 批量请求

        Returns:
            处理结果
        """
        # 轮询等待
        max_wait = 30  # 最多等待30秒
        wait_time = 0
        while not request.completed and wait_time < max_wait:
            await asyncio.sleep(0.01)
            wait_time += 0.01

        if not request.completed:
            raise TimeoutError(f"请求超时: {request.request_id}")

        if request.error:
            raise request.error

        return request.result

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息."""
        return {
            **self._stats,
            "queue_size": len(self._queue),
            "is_processing": self._processing,
        }


class ConcurrencyLimiter:
    """并发限制器.

    使用信号量控制并发数量.
    """

    def __init__(self, max_concurrent: int = 10):
        """初始化并发限制器.

        Args:
            max_concurrent: 最大并发数
        """
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks = 0
        self._lock = asyncio.Lock()

        # 统计信息
        self._stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "max_concurrent_reached": 0,
        }

        logger.info(f"并发限制器初始化: max_concurrent={max_concurrent}")

    async def run(self, coro):
        """运行协程（受并发限制）.

        Args:
            coro: 协程对象

        Returns:
            协程结果
        """
        async with self._lock:
            self._stats["total_tasks"] += 1

        # 等待信号量
        async with self._semaphore:
            async with self._lock:
                self._active_tasks += 1
                if self._active_tasks >= self.max_concurrent:
                    self._stats["max_concurrent_reached"] += 1

            try:
                result = await coro
                async with self._lock:
                    self._stats["completed_tasks"] += 1
                return result

            except Exception as e:
                async with self._lock:
                    self._stats["failed_tasks"] += 1
                raise e

            finally:
                async with self._lock:
                    self._active_tasks -= 1

    async def map(self, func: Callable, items: list[Any]) -> list[Any]:
        """并发映射.

        Args:
            func: 处理函数（可以是异步函数）
            items: 数据列表

        Returns:
            结果列表
        """
        tasks = []

        for item in items:
            if asyncio.iscoroutinefunction(func):
                coro = func(item)
            else:
                coro = asyncio.to_thread(func, item)

            tasks.append(self.run(coro))

        return await asyncio.gather(*tasks, return_exceptions=True)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息."""
        success_rate = (
            self._stats["completed_tasks"] / self._stats["total_tasks"] if self._stats["total_tasks"] > 0 else 0.0
        )

        return {
            **self._stats,
            "active_tasks": self._active_tasks,
            "success_rate": success_rate,
        }


class RequestDeduplicator:
    """请求去重器.

    合并相同的请求，避免重复调用.
    """

    def __init__(self, ttl: int = 60):
        """初始化去重器.

        Args:
            ttl: 缓存TTL（秒）
        """
        self.ttl = ttl
        self._cache: dict[str, Any] = {}
        self._timestamps: dict[str, datetime] = {}
        self._pending: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

        # 统计信息
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "pending_hits": 0,
            "cache_misses": 0,
        }

        logger.info(f"请求去重器初始化: ttl={ttl}s")

    def _make_key(self, *args, **kwargs) -> str:
        """生成缓存键."""
        import hashlib
        import json

        key_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    async def execute(self, key: str, func: Callable, *args, **kwargs) -> Any:
        """执行请求（带去重）.

        Args:
            key: 请求键
            func: 执行函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            执行结果
        """
        async with self._lock:
            self._stats["total_requests"] += 1

            # 检查缓存
            if key in self._cache:
                # 检查是否过期
                elapsed = (datetime.now() - self._timestamps[key]).total_seconds()
                if elapsed < self.ttl:
                    self._stats["cache_hits"] += 1
                    logger.debug(f"请求去重命中: {key}")
                    return self._cache[key]
                else:
                    # 过期，删除
                    del self._cache[key]
                    del self._timestamps[key]

            # 检查是否有pending请求
            if key in self._pending:
                self._stats["pending_hits"] += 1
                logger.debug(f"等待pending请求: {key}")
                future = self._pending[key]

        # 如果有pending，等待
        if key in self._pending:
            return await future

        # 创建新的future
        future = asyncio.Future()

        async with self._lock:
            self._pending[key] = future

        try:
            # 执行函数
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # 缓存结果
            async with self._lock:
                self._cache[key] = result
                self._timestamps[key] = datetime.now()
                self._stats["cache_misses"] += 1

            # 通知等待的请求
            future.set_result(result)

            return result

        except Exception as e:
            future.set_exception(e)
            raise

        finally:
            async with self._lock:
                if key in self._pending:
                    del self._pending[key]

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息."""
        total = self._stats["total_requests"]
        hit_rate = (self._stats["cache_hits"] + self._stats["pending_hits"]) / total if total > 0 else 0.0

        return {
            **self._stats,
            "cache_size": len(self._cache),
            "pending_size": len(self._pending),
            "hit_rate": hit_rate,
        }

    async def clear(self):
        """清空缓存."""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()


class BulkOperationManager:
    """批量操作管理器.

    集成批量处理、并发控制和请求去重.
    """

    def __init__(
        self,
        batch_size: int = 10,
        max_concurrent: int = 10,
        dedup_ttl: int = 60,
    ):
        """初始化批量操作管理器.

        Args:
            batch_size: 批量大小
            max_concurrent: 最大并发数
            dedup_ttl: 去重TTL（秒）
        """
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.dedup_ttl = dedup_ttl

        self.concurrency_limiter = ConcurrencyLimiter(max_concurrent)
        self.deduplicator = RequestDeduplicator(dedup_ttl)

        logger.info(
            "批量操作管理器初始化: "
            f"batch_size={batch_size}, "
            f"max_concurrent={max_concurrent}, "
            f"dedup_ttl={dedup_ttl}s"
        )

    async def execute_batch(
        self,
        items: list[Any],
        processor: Callable,
        dedupe_key: Callable[[Any], str] | None = None,
    ) -> list[Any]:
        """执行批量操作.

        Args:
            items: 数据列表
            processor: 处理函数
            dedupe_key: 去重键生成函数（可选）

        Returns:
            结果列表
        """
        # 分批处理
        results = []
        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]

            # 并发处理每个批次
            async def process_item(item):
                if dedupe_key:
                    key = dedupe_key(item)
                    return await self.deduplicator.execute(key, processor, item)
                else:
                    if asyncio.iscoroutinefunction(processor):
                        return await processor(item)
                    else:
                        return processor(item)

            batch_results = await self.concurrency_limiter.map(process_item, batch)
            results.extend(batch_results)

        return results

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息."""
        return {
            "concurrency": self.concurrency_limiter.get_stats(),
            "deduplication": self.deduplicator.get_stats(),
        }


# 全局批量操作管理器
_global_bulk_manager: BulkOperationManager | None = None


def get_bulk_manager() -> BulkOperationManager:
    """获取全局批量操作管理器.

    Returns:
        全局BulkOperationManager实例
    """
    global _global_bulk_manager
    if _global_bulk_manager is None:
        _global_bulk_manager = BulkOperationManager()
    return _global_bulk_manager


def set_bulk_manager(manager: BulkOperationManager):
    """设置全局批量操作管理器.

    Args:
        manager: BulkOperationManager实例
    """
    global _global_bulk_manager
    _global_bulk_manager = manager
