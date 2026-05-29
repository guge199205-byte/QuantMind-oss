import functools
import hashlib
import json
import logging
from typing import Any, Optional
from collections.abc import Callable

from backend.services.trade.redis_client import redis_client

logger = logging.getLogger(__name__)

def redis_cache(ttl: int = 60, prefix: str = "cache"):
    """
    Redis 缓存装饰器，专为 FastAPI 路由函数设计。
    自动识别身份标识 (user_id, tenant_id) 并进行数据隔离。
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 获取身份标识用于隔离
            # 尝试从参数中提取或者解析 AuthContext
            user_id = kwargs.get("user_id")
            tenant_id = kwargs.get("tenant_id")
            auth = kwargs.get("auth")

            # 如果存在 auth 对象，优先使用 auth 中的 identity
            if auth and hasattr(auth, 'user_id'):
                user_id = auth.user_id
                tenant_id = getattr(auth, 'tenant_id', 'default')

            # 构造缓存键基础部分
            # 键格式: {prefix}:{func_name}:{tenant_id}:{user_id}:{params_hash}
            resolved_tenant = str(tenant_id or "default")
            resolved_user = str(user_id or "unknown").zfill(8)

            # 生成参数哈希 (排除 db, redis, auth 等不可序列化对象)
            filtered_kwargs = {
                k: v for k, v in kwargs.items()
                if k not in {"db", "redis", "auth", "session"}
            }
            params_str = json.dumps(filtered_kwargs, sort_keys=True, default=str)
            params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]

            cache_key = f"{prefix}:{func.__name__}:{resolved_tenant}:{resolved_user}:{params_hash}"

            # 1. 尝试从缓存读取
            try:
                cached_data = redis_client.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Redis cache hit: {cache_key}")
                    return cached_data
            except Exception as e:
                logger.error(f"Redis cache read error: {e}")

            # 2. 执行原始函数
            result = await func(*args, **kwargs)

            # 3. 异步写入缓存
            try:
                if result is not None:
                    redis_client.set(cache_key, result, ttl=ttl)
                    logger.debug(f"Redis cache set: {cache_key} (ttl={ttl}s)")
            except Exception as e:
                logger.error(f"Redis cache write error: {e}")

            return result
        return wrapper
    return decorator
