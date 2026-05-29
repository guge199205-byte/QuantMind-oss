"""Redis rate limiting middleware (P2).

This is intentionally simple: fixed window counter using INCR + EXPIRE.
"""

from __future__ import annotations

import os
import time
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.services.api.community_app.auth import decode_token

try:
    from redis.asyncio import Redis  # type: ignore
except Exception:  # pragma: no cover
    Redis = None  # type: ignore


_redis: Redis | None = None


def _redis_url() -> str:
    url = os.getenv("REDIS_URL", "").strip()
    if url:
        return url
    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    password = os.getenv("REDIS_PASSWORD", "").strip()
    db = os.getenv("REDIS_DB", "0")
    auth = f":{password}@" if password else ""
    return f"redis://{auth}{host}:{port}/{db}"


async def _get_redis() -> Redis | None:
    global _redis
    if Redis is None:
        return None
    if _redis is None:
        _redis = Redis.from_url(_redis_url(), encoding="utf-8", decode_responses=True)
    return _redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, enabled: bool, window_seconds: int, max_requests: int):
        super().__init__(app)
        self.enabled = enabled
        self.window_seconds = window_seconds
        self.max_requests = max_requests

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        # Don't rate-limit health/metrics endpoints.
        if request.url.path in ("/health", "/metrics"):
            return await call_next(request)

        redis = await _get_redis()
        if redis is None:
            return await call_next(request)

        tenant_id = request.headers.get("x-tenant-id", "default")
        user_id = None

        # Prefer JWT principal if present (more accurate than header).
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            payload = decode_token(token)
            if payload:
                tenant_id = str(payload.get("tenant_id") or tenant_id)
                user_id = payload.get("user_id") or payload.get("sub")
                user_id = str(user_id) if user_id else None

        if not user_id:
            # Backward compatibility (gateway may choose to forward this internally).
            user_id = request.headers.get("x-user-id")

        if not user_id:
            # best-effort: fall back to IP
            user_id = (request.client.host if request.client else None) or "unknown"

        now = int(time.time())
        bucket = now // self.window_seconds
        key = f"rl:community:{tenant_id}:{user_id}:{bucket}"
        try:
            cnt = await redis.incr(key)
            if cnt == 1:
                await redis.expire(key, self.window_seconds + 2)
        except Exception:
            # Redis不可用时不阻断请求
            return await call_next(request)

        if cnt > self.max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "code": "RATE_LIMIT",
                    "window_seconds": self.window_seconds,
                    "max_requests": self.max_requests,
                },
            )

        return await call_next(request)
