"""
性能缓存模块
用于缓存QMT路径检测结果和其他耗时操作
"""

import hashlib
import json
import logging
import time
from functools import wraps
from typing import Any, Dict, Optional
from collections.abc import Callable

logger = logging.getLogger(__name__)


class PerformanceCache:
    """性能缓存管理器"""

    def __init__(self, default_ttl: int = 3600):
        """
        初始化缓存管理器

        Args:
            default_ttl: 默认缓存时间（秒），默认1小时
        """
        self._cache: dict[str, dict[str, Any]] = {}
        self.default_ttl = default_ttl

    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """
        生成缓存键

        Args:
            func_name: 函数名
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            缓存键
        """
        # 将参数序列化为字符串
        params_str = json.dumps(
            {"args": args, "kwargs": sorted(kwargs.items())},
            sort_keys=True,
            default=str,
        )

        # 生成哈希值
        params_hash = hashlib.md5(params_str.encode()).hexdigest()

        return f"{func_name}:{params_hash}"

    def get(self, key: str) -> Any | None:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期返回None
        """
        if key not in self._cache:
            return None

        cache_entry = self._cache[key]

        # 检查是否过期
        if time.time() > cache_entry["expires_at"]:
            del self._cache[key]
            return None

        logger.debug(f"Cache hit: {key}")
        return cache_entry["value"]

    def set(self, key: str, value: Any, ttl: int | None = None):
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 缓存时间（秒），None表示使用默认值
        """
        if ttl is None:
            ttl = self.default_ttl

        self._cache[key] = {
            "value": value,
            "expires_at": time.time() + ttl,
            "created_at": time.time(),
        }
        logger.debug(f"Cache set: {key} (TTL: {ttl}s)")

    def delete(self, key: str):
        """
        删除缓存值

        Args:
            key: 缓存键
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache deleted: {key}")

    def clear(self):
        """清空所有缓存"""
        self._cache.clear()
        logger.info("Cache cleared")

    def cleanup(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [key for key, entry in self._cache.items() if current_time > entry["expires_at"]]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

    def get_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        current_time = time.time()
        active_entries = sum(1 for entry in self._cache.values() if current_time <= entry["expires_at"])

        return {
            "total_entries": len(self._cache),
            "active_entries": active_entries,
            "expired_entries": len(self._cache) - active_entries,
        }

        # 全局缓存实例


_global_cache = PerformanceCache()


def cached(ttl: int | None = None, cache_instance: PerformanceCache | None = None):
    """
    缓存装饰器

    Args:
        ttl: 缓存时间（秒），None表示使用默认值
        cache_instance: 缓存实例，None表示使用全局实例

    Usage:
        @cached(ttl=300)
        def expensive_function(param1, param2):
            # 耗时操作
            return result
    """
    cache = cache_instance or _global_cache

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = cache._generate_key(func.__name__, args, kwargs)

            # 尝试从缓存获取
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

                # 执行函数
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time

            # 存入缓存
            cache.set(cache_key, result, ttl)

            logger.debug(
                f"Function {func.__name__} executed in {execution_time:.3f}s, " f"result cached with key {cache_key}"
            )

            return result

            # 添加缓存管理方法

        wrapper.cache_clear = lambda: cache.clear()
        wrapper.cache_info = lambda: cache.get_stats()

        return wrapper

    return decorator


def get_cache() -> PerformanceCache:
    """获取全局缓存实例"""
    return _global_cache
