"""熔断器和重试机制.

提供熔断器、智能重试和降级策略.

Author: QuantMind Team
Date: 2025-11-04
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from collections.abc import Callable

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态."""

    CLOSED = "closed"  # 正常
    OPEN = "open"  # 熔断
    HALF_OPEN = "half_open"  # 半开


class ErrorType(Enum):
    """错误类型."""

    NETWORK = "network"  # 网络错误
    TIMEOUT = "timeout"  # 超时
    RATE_LIMIT = "rate_limit"  # 限流
    SERVER_ERROR = "server_error"  # 服务器错误
    CLIENT_ERROR = "client_error"  # 客户端错误
    UNKNOWN = "unknown"  # 未知错误


@dataclass
class CircuitBreakerConfig:
    """熔断器配置."""

    failure_threshold: int = 5  # 失败阈值
    success_threshold: int = 2  # 成功阈值（半开状态）
    timeout: int = 60  # 熔断超时（秒）
    half_open_max_calls: int = 3  # 半开状态最大调用数


@dataclass
class RetryConfig:
    """重试配置."""

    max_attempts: int = 3  # 最大重试次数
    base_delay: float = 1.0  # 基础延迟（秒）
    max_delay: float = 60.0  # 最大延迟（秒）
    exponential_base: float = 2.0  # 指数退避基数
    jitter: bool = True  # 是否添加抖动


class CircuitBreaker:
    """熔断器.

    自动熔断失败的服务，防止雪崩.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        """初始化熔断器.

        Args:
            name: 熔断器名称
            config: 熔断器配置
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

        # 统计信息
        self._stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "rejected_calls": 0,
            "state_changes": 0,
        }

        logger.info(f"熔断器初始化: {name}")

    @property
    def state(self) -> CircuitState:
        """获取当前状态."""
        return self._state

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """执行调用（带熔断保护）.

        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果

        Raises:
            Exception: 熔断器打开或函数执行失败
        """
        async with self._lock:
            self._stats["total_calls"] += 1

            # 检查是否可以调用
            if not await self._can_execute():
                self._stats["rejected_calls"] += 1
                raise Exception(f"熔断器打开: {self.name}")

        # 执行调用
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self._on_success()
            return result

        except Exception as e:
            await self._on_failure(e)
            raise

    async def _can_execute(self) -> bool:
        """检查是否可以执行.

        Returns:
            是否可以执行
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # 检查是否超时
            if self._last_failure_time:
                elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                if elapsed >= self.config.timeout:
                    # 进入半开状态
                    await self._change_state(CircuitState.HALF_OPEN)
                    self._half_open_calls = 0
                    return True
            return False

        if self._state == CircuitState.HALF_OPEN:
            # 半开状态，限制调用数
            if self._half_open_calls < self.config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

        return False

    async def _on_success(self):
        """成功回调."""
        async with self._lock:
            self._stats["successful_calls"] += 1
            self._failure_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    await self._change_state(CircuitState.CLOSED)
                    self._success_count = 0

    async def _on_failure(self, error: Exception):
        """失败回调."""
        async with self._lock:
            self._stats["failed_calls"] += 1
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                # 半开状态失败，直接打开
                await self._change_state(CircuitState.OPEN)
                self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # 关闭状态，检查失败次数
                if self._failure_count >= self.config.failure_threshold:
                    await self._change_state(CircuitState.OPEN)

            logger.warning(f"熔断器 {self.name} 记录失败: {error}")

    async def _change_state(self, new_state: CircuitState):
        """改变状态."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            self._stats["state_changes"] += 1
            logger.info(f"熔断器 {self.name} 状态变更: {old_state.value} -> {new_state.value}")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息."""
        success_rate = (
            self._stats["successful_calls"] / self._stats["total_calls"] if self._stats["total_calls"] > 0 else 0.0
        )

        return {
            **self._stats,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_rate": success_rate,
        }

    async def reset(self):
        """重置熔断器."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            logger.info(f"熔断器 {self.name} 已重置")


class RetryStrategy:
    """重试策略.

    智能重试机制，支持指数退避和抖动.
    """

    def __init__(self, config: RetryConfig | None = None):
        """初始化重试策略.

        Args:
            config: 重试配置
        """
        self.config = config or RetryConfig()

        # 统计信息
        self._stats = {
            "total_attempts": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "total_delay": 0.0,
        }

        logger.info("重试策略初始化完成")

    def classify_error(self, error: Exception) -> ErrorType:
        """分类错误.

        Args:
            error: 异常对象

        Returns:
            错误类型
        """
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()

        if "timeout" in error_str or "timeout" in error_type:
            return ErrorType.TIMEOUT
        elif "rate limit" in error_str or "429" in error_str:
            return ErrorType.RATE_LIMIT
        elif "network" in error_str or "connection" in error_str or "temporary" in error_str:
            return ErrorType.NETWORK
        elif "500" in error_str or "502" in error_str or "503" in error_str:
            return ErrorType.SERVER_ERROR
        elif "400" in error_str or "401" in error_str or "403" in error_str:
            return ErrorType.CLIENT_ERROR
        else:
            return ErrorType.UNKNOWN

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """判断是否应该重试.

        Args:
            error: 异常对象
            attempt: 当前尝试次数

        Returns:
            是否应该重试
        """
        if attempt >= self.config.max_attempts:
            return False

        error_type = self.classify_error(error)

        # 可重试的错误类型
        retryable = {
            ErrorType.NETWORK,
            ErrorType.TIMEOUT,
            ErrorType.RATE_LIMIT,
            ErrorType.SERVER_ERROR,
        }

        return error_type in retryable

    def calculate_delay(self, attempt: int) -> float:
        """计算重试延迟.

        Args:
            attempt: 当前尝试次数

        Returns:
            延迟时间（秒）
        """
        # 指数退避
        delay = min(
            self.config.base_delay * (self.config.exponential_base**attempt),
            self.config.max_delay,
        )

        # 添加抖动
        if self.config.jitter:
            import random

            delay = delay * (0.5 + random.random() * 0.5)

        return delay

    async def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数（带重试）.

        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果

        Raises:
            Exception: 重试次数耗尽后的最后一个异常
        """
        last_error = None
        attempt = 0

        while attempt < self.config.max_attempts:
            self._stats["total_attempts"] += 1

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                if attempt > 0:
                    self._stats["successful_retries"] += 1
                    logger.info(f"重试成功: 第{attempt + 1}次尝试")

                return result

            except Exception as e:
                last_error = e
                attempt += 1

                if not self.should_retry(e, attempt):
                    logger.warning(f"错误不可重试: {self.classify_error(e).value}")
                    break

                if attempt < self.config.max_attempts:
                    delay = self.calculate_delay(attempt - 1)
                    self._stats["total_delay"] += delay

                    logger.info(f"重试 {attempt}/{self.config.max_attempts}: " f"延迟{delay:.2f}秒, 错误: {e}")

                    await asyncio.sleep(delay)
                else:
                    self._stats["failed_retries"] += 1

        # 所有重试都失败
        logger.error(f"重试次数耗尽: {last_error}")
        raise last_error

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息."""
        avg_delay = (
            self._stats["total_delay"] / self._stats["successful_retries"]
            if self._stats["successful_retries"] > 0
            else 0.0
        )

        return {
            **self._stats,
            "average_delay": avg_delay,
        }


class FallbackStrategy:
    """降级策略.

    提供服务降级和fallback功能.
    """

    def __init__(self):
        """初始化降级策略."""
        self._fallbacks: dict[str, Callable] = {}

        # 统计信息
        self._stats = {
            "total_fallbacks": 0,
            "cache_fallbacks": 0,
            "default_fallbacks": 0,
        }

        logger.info("降级策略初始化完成")

    def register_fallback(self, key: str, fallback: Callable):
        """注册fallback函数.

        Args:
            key: 键
            fallback: fallback函数
        """
        self._fallbacks[key] = fallback
        logger.debug(f"注册fallback: {key}")

    async def execute_with_fallback(
        self,
        func: Callable,
        fallback_key: str | None = None,
        default_value: Any = None,
        *args,
        **kwargs,
    ) -> Any:
        """执行函数（带降级）.

        Args:
            func: 主函数
            fallback_key: fallback键
            default_value: 默认值
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数结果或fallback结果
        """
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        except Exception as e:
            logger.warning(f"主函数失败，启用降级: {e}")
            self._stats["total_fallbacks"] += 1

            # 尝试fallback
            if fallback_key and fallback_key in self._fallbacks:
                fallback = self._fallbacks[fallback_key]
                try:
                    if asyncio.iscoroutinefunction(fallback):
                        result = await fallback(*args, **kwargs)
                    else:
                        result = fallback(*args, **kwargs)

                    logger.info(f"Fallback成功: {fallback_key}")
                    return result

                except Exception as fe:
                    logger.error(f"Fallback失败: {fe}")

            # 返回默认值
            self._stats["default_fallbacks"] += 1
            logger.info(f"使用默认值: {default_value}")
            return default_value

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息."""
        return self._stats.copy()


class ResilientClient:
    """弹性客户端.

    集成熔断器、重试和降级策略.
    """

    def __init__(
        self,
        name: str,
        circuit_config: CircuitBreakerConfig | None = None,
        retry_config: RetryConfig | None = None,
    ):
        """初始化弹性客户端.

        Args:
            name: 客户端名称
            circuit_config: 熔断器配置
            retry_config: 重试配置
        """
        self.name = name
        self.circuit_breaker = CircuitBreaker(name, circuit_config)
        self.retry_strategy = RetryStrategy(retry_config)
        self.fallback_strategy = FallbackStrategy()

        logger.info(f"弹性客户端初始化: {name}")

    async def execute(
        self,
        func: Callable,
        *args,
        fallback_key: str | None = None,
        default_value: Any = None,
        **kwargs,
    ) -> Any:
        """执行函数（全套保护）.

        Args:
            func: 要执行的函数
            fallback_key: fallback键
            default_value: 默认值
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数结果
        """

        async def protected_func():
            # 重试 + 熔断器
            async def call_with_breaker():
                return await self.circuit_breaker.call(func, *args, **kwargs)

            return await self.retry_strategy.execute_with_retry(call_with_breaker)

        # 降级
        return await self.fallback_strategy.execute_with_fallback(protected_func, fallback_key, default_value)

    def register_fallback(self, key: str, fallback: Callable):
        """注册fallback."""
        self.fallback_strategy.register_fallback(key, fallback)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息."""
        return {
            "circuit_breaker": self.circuit_breaker.get_stats(),
            "retry": self.retry_strategy.get_stats(),
            "fallback": self.fallback_strategy.get_stats(),
        }


# 全局弹性客户端管理
_global_clients: dict[str, ResilientClient] = {}


def get_resilient_client(
    name: str,
    circuit_config: CircuitBreakerConfig | None = None,
    retry_config: RetryConfig | None = None,
) -> ResilientClient:
    """获取弹性客户端.

    Args:
        name: 客户端名称
        circuit_config: 熔断器配置
        retry_config: 重试配置

    Returns:
        ResilientClient实例
    """
    if name not in _global_clients:
        _global_clients[name] = ResilientClient(name, circuit_config, retry_config)
    return _global_clients[name]
