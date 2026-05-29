"""
审计日志中间件
"""

import logging
import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.services.api.user_app.services.enhanced_audit_service import (
    EnhancedAuditService,
)
from backend.shared.database_manager_v2 import get_session

logger = logging.getLogger(__name__)


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    审计日志中间件

    自动记录所有API请求的审计日志
    """

    def __init__(self, app, exempt_paths: list = None):
        super().__init__(app)
        # 豁免路径（不记录审计日志）
        self.exempt_paths = exempt_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    def should_log(self, path: str) -> bool:
        """判断是否应该记录审计日志"""
        return not any(path.startswith(exempt) for exempt in self.exempt_paths)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        # 检查是否需要记录审计日志
        if not self.should_log(request.url.path):
            return await call_next(request)

        # 记录开始时间
        start_time = time.time()

        # 获取用户信息
        user = getattr(request.state, "user", None)
        user_id = user.get("user_id") if user else "anonymous"
        tenant_id = user.get("tenant_id") if user else None

        # 获取请求信息
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")
        request_method = request.method
        request_path = str(request.url.path)

        # 解析资源类型和操作
        resource, action = self._parse_resource_action(request_method, request_path)

        # 执行请求
        response = None
        error_message = None
        success = True

        try:
            response = await call_next(request)
            success = 200 <= response.status_code < 400
            return response
        except Exception as e:
            logger.error(f"Request error: {e}")
            error_message = str(e)
            success = False
            raise
        finally:
            # 计算处理时长
            duration_ms = int((time.time() - start_time) * 1000)

            # 异步记录审计日志
            if user_id != "anonymous" and tenant_id:
                try:
                    async with get_session(read_only=False) as session:
                        audit_service = EnhancedAuditService(session)
                        await audit_service.log_operation(
                            user_id=user_id,
                            tenant_id=tenant_id,
                            action=action,
                            resource=resource,
                            ip_address=ip_address,
                            user_agent=user_agent,
                            request_method=request_method,
                            request_path=request_path,
                            status_code=response.status_code if response else 500,
                            success=success,
                            error_message=error_message,
                            duration_ms=duration_ms,
                        )
                except Exception as e:
                    # 记录审计日志失败不应影响正常请求
                    logger.error(f"Failed to log audit: {e}")

    def _parse_resource_action(self, method: str, path: str) -> tuple:
        """
        解析资源类型和操作

        Returns:
            (resource, action) 元组
        """
        # 默认映射
        action_mapping = {
            "GET": "read",
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete",
        }
        action = action_mapping.get(method, "unknown")

        # 从路径解析资源类型
        parts = path.split("/")
        if len(parts) >= 4:  # /api/v1/users/...
            resource = parts[3]
        else:
            resource = "unknown"

        # 特殊处理
        if "login" in path:
            action = "login"
            resource = "auth"
        elif "logout" in path:
            action = "logout"
            resource = "auth"
        elif "register" in path:
            action = "register"
            resource = "auth"

        return resource, action
