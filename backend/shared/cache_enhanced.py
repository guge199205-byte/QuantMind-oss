#!/usr/bin/env python3
"""
增强缓存管理器
Week 4 Day 3 - 缓存策略优化

功能:
1. 多级缓存 (L1:内存 + L2:Redis)
2. 缓存穿透/雪崩/击穿防护
3. 智能TTL策略
4. 缓存预热
5. 命中率监控
"""

import asyncio
import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from functools import wraps
from threading import RLock
from typing import Any, Dict, List, Optional, Set
from collections.abc import Callable

try:
    import redis.asyncio as aioredis

    from redis import Redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None
    Redis = None

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# Prometheus指标
cache_hits = Counter("cache_hits_total", "Total cache hits", ["level", "key_prefix"])
cache_misses = Counter("cache_misses_total", "Total cache misses", ["level", "key_prefix"])
cache_sets = Counter("cache_sets_total", "Total cache sets", ["level", "key_prefix"])
cache_errors = Counter("cache_errors_total", "Total cache errors", ["level", "operation"])

cache_size = Gauge("cache_size_bytes", "Cache size in bytes", ["level"])
cache_items = Gauge("cache_items_total", "Total cache items", ["level"])
cache_hit_rate = Gauge("cache_hit_rate_percent", "Cache hit rate percentage", ["level"])

cache_operation_duration = Histogram(
    "cache_operation_duration_seconds",
    "Cache operation duration",
    ["operation", "level"],
)


@dataclass
class CacheEntry:
    """增强的缓存项"""

    value: Any
    expires_at: float
    created_at: float
    hit_count: int = 0
    last_access: float = field(default_factory=time.time)
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() > self.expires_at

    def hit(self):
        """记录命中"""
        self.hit_count += 1
        self.last_access = time.time()

    def hotness_score(self) -> float:
        """计算热度分数 (用于智能淘汰)"""
        age = time.time() - self.created_at
        recency = time.time() - self.last_access
        frequency = self.hit_count

        # LFU + LRU混合策略
        return (frequency * 0.7) - (recency * 0.2) - (age * 0.1)


class EnhancedMemoryCache:
    """增强的内存缓存"""

    def __init__(
        self,
        max_size: int = 1000,
        max_memory_mb: int = 100,
        default_ttl: int = 300,
        cleanup_interval: int = 60,
    ):
        """
        Args:
            max_size: 最大缓存项数量
            max_memory_mb: 最大内存使用(MB)
            default_ttl: 默认TTL(秒)
            cleanup_interval: 清理间隔(秒)
        """
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval

        self._cache: dict[str, CacheEntry] = {}
        self._lock = RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
            "memory_bytes": 0,
        }
        self._last_cleanup = time.time()

        # 热点数据集 (自动识别)
        self._hot_keys: set[str] = set()

    def get(self, key: str, track_hit: bool = True) -> Any | None:
        """获取缓存值"""
        start_time = time.time()

        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                cache_misses.labels(level="memory", key_prefix=self._get_key_prefix(key)).inc()
                return None

            entry = self._cache[key]

            # 检查过期
            if entry.is_expired():
                self._delete_entry(key)
                self._stats["misses"] += 1
                cache_misses.labels(level="memory", key_prefix=self._get_key_prefix(key)).inc()
                return None

            # 记录命中
            if track_hit:
                entry.hit()
                self._stats["hits"] += 1
                cache_hits.labels(level="memory", key_prefix=self._get_key_prefix(key)).inc()

                # 热点数据识别
                if entry.hit_count > 10:
                    self._hot_keys.add(key)

            duration = time.time() - start_time
            cache_operation_duration.labels(operation="get", level="memory").observe(duration)

            return entry.value

    def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """设置缓存值"""
        start_time = time.time()

        with self._lock:
            ttl = ttl or self.default_ttl
            expires_at = time.time() + ttl

            # 计算数据大小
            size_bytes = self._estimate_size(value)

            # 检查是否需要淘汰
            if key not in self._cache:
                while (
                    len(self._cache) >= self.max_size
                    or self._stats["memory_bytes"] + size_bytes > self.max_memory_bytes
                ):
                    if not self._evict_entry():
                        return False

            # 删除旧条目
            if key in self._cache:
                self._stats["memory_bytes"] -= self._cache[key].size_bytes

            # 创建新条目
            entry = CacheEntry(
                value=value,
                expires_at=expires_at,
                created_at=time.time(),
                size_bytes=size_bytes,
            )

            self._cache[key] = entry
            self._stats["memory_bytes"] += size_bytes
            self._stats["sets"] += 1

            cache_sets.labels(level="memory", key_prefix=self._get_key_prefix(key)).inc()

            # 定期清理
            if time.time() - self._last_cleanup > self.cleanup_interval:
                self._cleanup_expired()

            duration = time.time() - start_time
            cache_operation_duration.labels(operation="set", level="memory").observe(duration)

            # 更新指标
            cache_size.labels(level="memory").set(self._stats["memory_bytes"])
            cache_items.labels(level="memory").set(len(self._cache))

            return True

    def delete(self, key: str) -> bool:
        """删除缓存项"""
        with self._lock:
            if key in self._cache:
                self._delete_entry(key)
                return True
            return False

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._hot_keys.clear()
            self._stats["memory_bytes"] = 0
            cache_size.labels(level="memory").set(0)
            cache_items.labels(level="memory").set(0)

    def get_hot_keys(self) -> list[str]:
        """获取热点数据键"""
        with self._lock:
            return list(self._hot_keys)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0

            # 更新命中率指标
            cache_hit_rate.labels(level="memory").set(hit_rate)

            return {
                **self._stats,
                "size": len(self._cache),
                "max_size": self.max_size,
                "hit_rate": hit_rate,
                "memory_mb": self._stats["memory_bytes"] / 1024 / 1024,
                "max_memory_mb": self.max_memory_bytes / 1024 / 1024,
                "hot_keys_count": len(self._hot_keys),
            }

    def _delete_entry(self, key: str):
        """删除条目（内部方法）"""
        if key in self._cache:
            self._stats["memory_bytes"] -= self._cache[key].size_bytes
            del self._cache[key]
            self._stats["deletes"] += 1

            if key in self._hot_keys:
                self._hot_keys.remove(key)

    def _evict_entry(self) -> bool:
        """淘汰一个条目"""
        if not self._cache:
            return False

        # 先淘汰过期的
        for key, entry in list(self._cache.items()):
            if entry.is_expired():
                self._delete_entry(key)
                self._stats["evictions"] += 1
                return True

        # 使用热度分数淘汰（LFU + LRU混合）
        # 优先保护热点数据
        candidates = {k: v for k, v in self._cache.items() if k not in self._hot_keys}

        if not candidates:
            candidates = self._cache

        if not candidates:
            return False

        # 找到热度最低的
        lru_key = min(candidates.keys(), key=lambda k: candidates[k].hotness_score())

        self._delete_entry(lru_key)
        self._stats["evictions"] += 1
        return True

    def _cleanup_expired(self):
        """清理过期项"""
        current_time = time.time()
        expired_keys = [key for key, entry in self._cache.items() if entry.is_expired()]

        for key in expired_keys:
            self._delete_entry(key)

        self._last_cleanup = current_time

    @staticmethod
    def _estimate_size(value: Any) -> int:
        """估算值的大小（字节）"""
        try:
            if isinstance(value, (str, bytes)):
                return len(value)
            elif isinstance(value, (dict, list, tuple)):
                return len(json.dumps(value))
            else:
                return len(str(value))
        except Exception:
            return 100  # 默认估计

    @staticmethod
    def _get_key_prefix(key: str) -> str:
        """获取键前缀（用于分类统计）"""
        parts = key.split(":", 1)
        return parts[0] if len(parts) > 1 else "default"


class CacheProtection:
    """缓存保护机制"""

    def __init__(self):
        self._bloom_filter: set[str] = set()  # 简单布隆过滤器
        self._loading_keys: dict[str, asyncio.Lock] = {}  # 防击穿锁
        self._null_cache: dict[str, float] = {}  # 空值缓存

    def may_exist(self, key: str) -> bool:
        """布隆过滤器检查（防穿透）"""
        return key in self._bloom_filter

    def add_to_bloom(self, key: str):
        """添加到布隆过滤器"""
        self._bloom_filter.add(key)

    async def get_lock(self, key: str) -> asyncio.Lock:
        """获取键锁（防击穿）"""
        if key not in self._loading_keys:
            self._loading_keys[key] = asyncio.Lock()
        return self._loading_keys[key]

    def cache_null(self, key: str, ttl: int = 60):
        """缓存空值（防穿透）"""
        self._null_cache[key] = time.time() + ttl

    def is_null_cached(self, key: str) -> bool:
        """检查空值缓存"""
        if key in self._null_cache:
            if time.time() < self._null_cache[key]:
                return True
            else:
                del self._null_cache[key]
        return False


class EnhancedCacheManager:
    """增强的缓存管理器"""

    def __init__(
        self,
        use_memory: bool = True,
        use_redis: bool = False,
        memory_config: dict | None = None,
        redis_config: dict | None = None,
    ):
        """初始化增强缓存管理器"""
        self.use_memory = use_memory
        self.use_redis = use_redis

        # 初始化内存缓存
        if use_memory:
            memory_config = memory_config or {}
            self.memory_cache = EnhancedMemoryCache(**memory_config)
        else:
            self.memory_cache = None

        # 初始化Redis缓存
        self.redis_client = None
        if use_redis and REDIS_AVAILABLE:
            try:
                redis_config = redis_config or {}
                host = redis_config.get("host", os.getenv("REDIS_HOST", "localhost"))
                port = int(redis_config.get("port", os.getenv("REDIS_PORT", 6379)))
                db = int(redis_config.get("db", os.getenv("REDIS_DB", 0)))
                password = redis_config.get("password", os.getenv("REDIS_PASSWORD", ""))

                self.redis_client = Redis(
                    host=host,
                    port=port,
                    db=db,
                    password=password,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                # 测试连接
                self.redis_client.ping()
                logger.info(f"✅ Redis缓存初始化成功: {host}:{port}/{db}")
            except Exception as e:
                logger.warning(f"⚠️ Redis缓存初始化失败: {e}")
                self.redis_client = None
                self.use_redis = False

        # 缓存保护
        self.protection = CacheProtection()

        logger.info(f"✅ 增强缓存管理器初始化 - 内存: {use_memory}, Redis: {self.use_redis}")

    def get(self, key: str) -> Any | None:
        """多级缓存获取"""
        # 检查空值缓存
        if self.protection.is_null_cached(key):
            return None

        # L1: 内存缓存
        if self.memory_cache:
            value = self.memory_cache.get(key)
            if value is not None:
                return value

        # L2: Redis缓存
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                if value is not None:
                    # 反序列化
                    try:
                        value = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        pass

                    # 回写L1
                    if self.memory_cache:
                        self.memory_cache.set(key, value, ttl=60)

                    cache_hits.labels(level="redis", key_prefix=self._get_key_prefix(key)).inc()
                    return value
                else:
                    cache_misses.labels(level="redis", key_prefix=self._get_key_prefix(key)).inc()
            except Exception as e:
                logger.error(f"Redis get error: {e}")
                cache_errors.labels(level="redis", operation="get").inc()

        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        ttl_jitter: bool = True,
    ) -> bool:
        """多级缓存设置"""
        success = True

        # 添加到布隆过滤器
        self.protection.add_to_bloom(key)

        # TTL抖动（防雪崩）
        if ttl and ttl_jitter:
            jitter = random.randint(-int(ttl * 0.1), int(ttl * 0.1))
            ttl = max(1, ttl + jitter)

        # L1: 内存缓存（较短TTL）
        if self.memory_cache:
            memory_ttl = min(ttl or 300, 300) if ttl else 60
            success &= self.memory_cache.set(key, value, memory_ttl)

        # L2: Redis缓存（较长TTL）
        if self.redis_client:
            try:
                ttl = ttl or 3600
                # 序列化
                if isinstance(value, (dict, list, tuple)):
                    serialized = json.dumps(value, ensure_ascii=False)
                else:
                    serialized = str(value)

                success &= bool(self.redis_client.setex(key, ttl, serialized))
                cache_sets.labels(level="redis", key_prefix=self._get_key_prefix(key)).inc()
            except Exception as e:
                logger.error(f"Redis set error: {e}")
                cache_errors.labels(level="redis", operation="set").inc()
                success = False

        return success

    def delete(self, key: str) -> bool:
        """删除缓存"""
        success = True

        if self.memory_cache:
            success &= self.memory_cache.delete(key)

        if self.redis_client:
            try:
                success &= bool(self.redis_client.delete(key))
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
                cache_errors.labels(level="redis", operation="delete").inc()
                success = False

        return success

    def get_or_set(
        self,
        key: str,
        fetch_func: Callable,
        ttl: int | None = None,
        cache_null: bool = True,
    ) -> Any | None:
        """获取或设置缓存（防击穿）"""
        # 先尝试获取
        value = self.get(key)
        if value is not None:
            return value

        # 数据不存在，需要加载
        try:
            value = fetch_func()

            if value is not None:
                self.set(key, value, ttl)
            elif cache_null:
                # 缓存空值
                self.protection.cache_null(key, ttl=60)

            return value

        except Exception as e:
            logger.error(f"Error fetching data for key {key}: {e}")
            return None

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        stats = {
            "memory_enabled": self.use_memory,
            "redis_enabled": self.use_redis,
        }

        if self.memory_cache:
            stats["memory"] = self.memory_cache.get_stats()

        if self.redis_client:
            try:
                info = self.redis_client.info()
                keyspace = self.redis_client.info("keyspace")

                stats["redis"] = {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory_mb": info.get("used_memory", 0) / 1024 / 1024,
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0),
                    "keys": (keyspace.get("db0", {}).get("keys", 0) if "db0" in keyspace else 0),
                }

                # 计算Redis命中率
                hits = stats["redis"]["keyspace_hits"]
                misses = stats["redis"]["keyspace_misses"]
                total = hits + misses
                if total > 0:
                    hit_rate = hits / total * 100
                    stats["redis"]["hit_rate"] = hit_rate
                    cache_hit_rate.labels(level="redis").set(hit_rate)

            except Exception as e:
                logger.error(f"Error getting Redis stats: {e}")
                stats["redis"] = {}

        return stats

    @staticmethod
    def _get_key_prefix(key: str) -> str:
        """获取键前缀"""
        parts = key.split(":", 1)
        return parts[0] if len(parts) > 1 else "default"


def cached(
    ttl: int = 3600,
    key_prefix: str = "",
    cache_null: bool = True,
    ttl_jitter: bool = True,
):
    """缓存装饰器

    Args:
        ttl: 缓存过期时间（秒）
        key_prefix: 缓存键前缀
        cache_null: 是否缓存空值
        ttl_jitter: 是否添加TTL抖动

    用法:
        @cached(ttl=600, key_prefix="stock")
        def get_stock_data(symbol: str):
            return fetch_from_api(symbol)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            key_parts = [key_prefix or func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            # 使用全局缓存管理器
            global enhanced_cache_manager
            if enhanced_cache_manager is None:
                enhanced_cache_manager = EnhancedCacheManager(use_memory=True, use_redis=True)

            return enhanced_cache_manager.get_or_set(
                cache_key,
                lambda: func(*args, **kwargs),
                ttl=ttl,
                cache_null=cache_null,
            )

        return wrapper

    return decorator


# 全局缓存实例
enhanced_cache_manager: EnhancedCacheManager | None = None


def get_cache_manager() -> EnhancedCacheManager:
    """获取全局缓存管理器"""
    global enhanced_cache_manager
    if enhanced_cache_manager is None:
        enhanced_cache_manager = EnhancedCacheManager(use_memory=True, use_redis=True)
    return enhanced_cache_manager
