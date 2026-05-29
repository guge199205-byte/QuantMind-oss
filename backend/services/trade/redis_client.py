"""
Redis connection and cache management
"""

import json
import logging
from typing import Any, Optional

import redis
from backend.services.trade.trade_config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client wrapper"""

    def __init__(self):
        self.client: redis.Redis | None = None

    def connect(self):
        """Connect to Redis"""
        try:
            if settings.REDIS_SENTINEL_ENABLED:
                from redis.sentinel import Sentinel

                sentinel_hosts = [tuple(host.split(":")) for host in settings.REDIS_SENTINEL_HOSTS.split(",")]
                sentinel = Sentinel(sentinel_hosts, socket_timeout=5.0, password=settings.REDIS_PASSWORD)
                self.client = sentinel.master_for(
                    settings.REDIS_MASTER_NAME,
                    socket_timeout=5.0,
                    db=settings.REDIS_DB,
                    decode_responses=True,
                )
                logger.info(f"Connected to Redis Sentinel: {settings.REDIS_MASTER_NAME}")
            else:
                self.client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    password=settings.REDIS_PASSWORD,
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                )
                logger.info(f"Connected to Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")

            # Test connection
            self.client.ping()

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None

    def close(self):
        """Close Redis connection"""
        if self.client:
            self.client.close()
            logger.info("Redis connection closed")

    def get(self, key: str) -> Any | None:
        """Get value from cache"""
        if not self.client:
            return None
        try:
            value = self.client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int | None = None):
        """Set value in cache"""
        if not self.client:
            return
        try:
            self.client.set(key, json.dumps(value), ex=ttl)
        except Exception as e:
            logger.error(f"Redis SET error: {e}")

    def delete(self, key: str):
        """Delete key from cache"""
        if not self.client:
            return
        try:
            self.client.delete(key)
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")

    def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern"""
        if not self.client:
            return
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
                logger.debug(f"Deleted {len(keys)} keys matching pattern: {pattern}")
        except Exception as e:
            logger.error(f"Redis DELETE_PATTERN error: {e}")

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.client:
            return False
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return False

    def publish_event(self, stream_name: str, event_data: dict):
        """Publish event to Redis Stream"""
        if not self.client:
            return
        try:
            # Flatten dict for Redis XADD (all values must be strings/bytes)
            flat_data = {k: str(v) for k, v in event_data.items()}
            self.client.xadd(stream_name, flat_data)
            logger.debug(f"Event published to {stream_name}")
        except Exception as e:
            logger.error(f"Redis XADD error: {e}")


# Global Redis client instance
redis_client = RedisClient()


def get_redis() -> RedisClient:
    """Get Redis client, ensuring it is connected"""
    if redis_client.client is None:
        logger.info("Initializing Redis connection on first access...")
        redis_client.connect()
    return redis_client
