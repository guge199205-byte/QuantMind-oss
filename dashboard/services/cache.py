"""
Redis 缓存服务

缓存频繁查询的数据，减少数据库压力。
"""

import os
import json
import logging
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = 5  # 使用 DB5 作为 Dashboard 缓存

_redis_client = None


def _get_redis() -> Optional[redis.Redis]:
    """获取 Redis 连接"""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            _redis_client.ping()
        except Exception as e:
            logger.warning("Redis connection failed: %s", e)
            _redis_client = None
    return _redis_client


def check_redis() -> bool:
    """检查 Redis 连接状态"""
    r = _get_redis()
    return r is not None


def get(key: str) -> Optional[Any]:
    """从缓存获取数据"""
    r = _get_redis()
    if not r:
        return None

    try:
        data = r.get(f"dashboard:{key}")
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning("Cache get failed for %s: %s", key, e)

    return None


def set(key: str, value: Any, ttl: int = 300) -> bool:
    """设置缓存数据

    Args:
        key: 缓存键
        value: 缓存值（会被 JSON 序列化）
        ttl: 过期时间（秒），默认 5 分钟
    """
    r = _get_redis()
    if not r:
        return False

    try:
        data = json.dumps(value, ensure_ascii=False, default=str)
        r.setex(f"dashboard:{key}", ttl, data)
        return True
    except Exception as e:
        logger.warning("Cache set failed for %s: %s", key, e)
        return False


def delete(key: str) -> bool:
    """删除缓存"""
    r = _get_redis()
    if not r:
        return False

    try:
        r.delete(f"dashboard:{key}")
        return True
    except Exception as e:
        logger.warning("Cache delete failed for %s: %s", key, e)
        return False


def clear_pattern(pattern: str) -> int:
    """清除匹配模式的缓存"""
    r = _get_redis()
    if not r:
        return 0

    try:
        keys = r.keys(f"dashboard:{pattern}")
        if keys:
            return r.delete(*keys)
    except Exception as e:
        logger.warning("Cache clear pattern failed for %s: %s", pattern, e)

    return 0


def cached(key: str, ttl: int = 300):
    """缓存装饰器

    用法:
        @cached("stock_daily:600519", ttl=600)
        def get_stock_data():
            return expensive_query()
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 尝试从缓存获取
            cache_key = key
            if args or kwargs:
                cache_key = f"{key}:{hash(str(args) + str(kwargs))}"

            cached_data = get(cache_key)
            if cached_data is not None:
                return cached_data

            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            if result is not None:
                set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
