"""
Cache Service - 缓存服务
"""

import json
import logging
import pickle
from typing import Any, Optional

from backend.shared.redis_sentinel_client import get_redis_sentinel_client

logger = logging.getLogger(__name__)


class CacheService:
    """缓存服务"""

    def __init__(self):
        self.redis_client = get_redis_sentinel_client()

    def get(self, key: str, use_slave: bool = True) -> bytes | None:
        """获取缓存"""
        try:
            value = self.redis_client.get(key, use_slave=use_slave)
            if value:
                logger.debug(f"Cache hit: {key}")
            return value
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    def set(self, key: str, value: bytes, ttl: int | None = None, use_slave: bool = False) -> bool:
        """设置缓存"""
        try:
            if ttl:
                self.redis_client.setex(key, ttl, value)
            else:
                self.redis_client.set(key, value)
            logger.debug(f"Cache set: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            result = self.redis_client.delete(key)
            logger.debug(f"Cache delete: {key}")
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    def get_json(self, key: str, use_slave: bool = True) -> dict | None:
        """获取JSON格式缓存"""
        value = self.get(key, use_slave)
        if value:
            try:
                return json.loads(value.decode())
            except Exception as e:
                logger.error(f"JSON decode error: {e}")
        return None

    def set_json(self, key: str, value: dict, ttl: int | None = None) -> bool:
        """设置JSON格式缓存"""
        try:
            json_str = json.dumps(value)
            return self.set(key, json_str.encode(), ttl)
        except Exception as e:
            logger.error(f"JSON encode error: {e}")
            return False

    def get_object(self, key: str, use_slave: bool = True) -> Any | None:
        """获取Python对象缓存"""
        value = self.get(key, use_slave)
        if value:
            try:
                return pickle.loads(value)
            except Exception as e:
                logger.error(f"Pickle decode error: {e}")
        return None

    def set_object(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """设置Python对象缓存"""
        try:
            pickled = pickle.dumps(value)
            return self.set(key, pickled, ttl)
        except Exception as e:
            logger.error(f"Pickle encode error: {e}")
            return False

    def exists(self, key: str) -> bool:
        """检查key是否存在"""
        try:
            return self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            return False

    def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间"""
        try:
            return self.redis_client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Cache expire error: {e}")
            return False

    def ttl(self, key: str) -> int | None:
        """获取剩余生存时间"""
        try:
            return self.redis_client.ttl(key)
        except Exception as e:
            logger.error(f"Cache ttl error: {e}")
            return None

    def delete_pattern(self, pattern: str) -> int:
        """删除匹配模式的所有key"""
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error: {e}")
            return 0

    def increment(self, key: str, amount: int = 1) -> int | None:
        """递增计数器"""
        try:
            return self.redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error: {e}")
            return None

    def decrement(self, key: str, amount: int = 1) -> int | None:
        """递减计数器"""
        try:
            return self.redis_client.decrby(key, amount)
        except Exception as e:
            logger.error(f"Cache decrement error: {e}")
            return None


# 全局缓存服务实例
_cache_service = None


def get_cache_service() -> CacheService:
    """获取缓存服务单例"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
