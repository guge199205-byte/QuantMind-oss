"""
多级缓存管理器
实现 L1 (内存) -> L2 (Redis) -> L3 (数据库) 三级缓存架构
"""

import asyncio
import json
import logging
import time
from functools import wraps
from typing import Any, Dict, Optional
from collections.abc import Callable

logger = logging.getLogger(__name__)


class LocalMemoryCache:
    """L1: 本地内存缓存 - 热点数据"""

    def __init__(self, max_size: int = 1000, default_ttl: int = 60):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Any | None:
        if key not in self._cache:
            self._misses += 1
            return None
        value, expire_at = self._cache[key]
        if expire_at > 0 and time.time() > expire_at:
            del self._cache[key]
            self._misses += 1
            return None
        self._hits += 1
        return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        if len(self._cache) >= self._max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        ttl = ttl or self._default_ttl
        expire_at = time.time() + ttl if ttl > 0 else 0
        self._cache[key] = (value, expire_at)
        return True

    async def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%",
        }


class MultiLevelCache:
    """多级缓存管理器 L1 (内存) -> L2 (Redis) -> L3 (数据源)"""

    def __init__(
        self,
        redis_client=None,
        l1_max_size: int = 1000,
        l1_ttl: int = 60,
        l2_ttl: int = 300,
    ):
        self.l1 = LocalMemoryCache(max_size=l1_max_size, default_ttl=l1_ttl)
        self._redis = redis_client
        self._l1_ttl = l1_ttl
        self._l2_ttl = l2_ttl

    async def get(
        self,
        key: str,
        loader: Callable | None = None,
        ttl_l1: int | None = None,
        ttl_l2: int | None = None,
    ) -> Any | None:
        """获取缓存值，支持三级缓存穿透"""
        ttl_l1 = ttl_l1 or self._l1_ttl
        ttl_l2 = ttl_l2 or self._l2_ttl

        value = await self.l1.get(key)
        if value is not None:
            return value

        if self._redis:
            try:
                cached = await self._redis.get(key)
                if cached:
                    value = json.loads(cached)
                    await self.l1.set(key, value, ttl=ttl_l1)
                    return value
            except Exception as e:
                logger.error(f"Redis error: {e}")

        if loader:
            value = await loader() if asyncio.iscoroutinefunction(loader) else loader()
            if value is not None:
                await self.set(key, value, ttl_l1=ttl_l1, ttl_l2=ttl_l2)
            return value
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl_l1: int | None = None,
        ttl_l2: int | None = None,
    ) -> bool:
        """设置缓存值到所有层"""
        ttl_l1 = ttl_l1 or self._l1_ttl
        ttl_l2 = ttl_l2 or self._l2_ttl
        await self.l1.set(key, value, ttl=ttl_l1)
        if self._redis:
            try:
                await self._redis.setex(key, ttl_l2, json.dumps(value))
            except Exception as e:
                logger.error(f"Redis set error: {e}")
        return True

    async def delete(self, key: str) -> bool:
        """删除所有层的缓存"""
        await self.l1.delete(key)
        if self._redis:
            try:
                await self._redis.delete(key)
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
        return True

    def cached(
        self,
        prefix: str = "",
        ttl_l1: int | None = None,
        ttl_l2: int | None = None,
    ):
        """缓存装饰器"""

        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                key_parts = [prefix] if prefix else []
                key_parts.extend(str(arg) for arg in args)
                cache_key = ":".join(key_parts)

                async def loader():
                    return await func(*args, **kwargs)

                return await self.get(cache_key, loader=loader, ttl_l1=ttl_l1, ttl_l2=ttl_l2)

            return wrapper

        return decorator

    def get_stats(self) -> dict[str, Any]:
        return {"l1": self.l1.get_stats(), "l2": {"enabled": self._redis is not None}}
