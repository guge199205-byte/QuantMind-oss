"""
Logging Middleware
"""

import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # 记录请求
        logger.info(f"Request: {request.method} {request.url.path}")

        # 处理请求
        response = await call_next(request)

        # 记录响应
        process_time = time.time() - start_time
        logger.info(f"Response: {response.status_code} | Time: {process_time:.3f}s")

        # 添加响应头
        response.headers["X-Process-Time"] = str(process_time)

        return response
