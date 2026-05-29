"""
安全增强模块
"""

import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import bcrypt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt

logger = logging.getLogger(__name__)


class SecurityService:
    """安全服务类"""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.algorithm = "HS256"
        self.security = HTTPBearer()

    def hash_password(self, password: str) -> str:
        """密码哈希"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    def create_jwt_token(self, user_id: str, permissions: list = None) -> str:
        """创建JWT Token"""
        payload = {
            "user_id": user_id,
            "permissions": permissions or [],
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1),
            "jti": secrets.token_urlsafe(32),  # JWT ID防止重放攻击
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_jwt_token(self, token: str) -> dict[str, Any] | None:
        """验证JWT Token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    def generate_api_key(self, user_id: str, permissions: list = None) -> str:
        """生成API密钥"""
        key = f"qm_{secrets.token_urlsafe(32)}"
        # 这里应该将密钥存储到数据库
        return key

    async def verify_token(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
        """验证Token的依赖函数"""
        token = credentials.credentials
        return self.verify_jwt_token(token)


class RateLimiter:
    """请求限流器"""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}

    def is_allowed(self, client_id: str) -> bool:
        """检查是否允许请求"""
        now = time.time()
        window_start = now - self.window_seconds

        # 清理过期的请求记录
        if client_id in self.requests:
            self.requests[client_id] = [req_time for req_time in self.requests[client_id] if req_time > window_start]
        else:
            self.requests[client_id] = []

        # 检查请求数量
        if len(self.requests[client_id]) >= self.max_requests:
            return False

        # 记录新请求
        self.requests[client_id].append(now)
        return True

    def get_client_id(self, request: Request) -> str:
        """获取客户端ID"""
        # 优先使用X-Forwarded-For，否则使用remote_addr
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host


class XSSProtection:
    """XSS防护"""

    @staticmethod
    def sanitize_input(input_str: str) -> str:
        """清理用户输入"""
        import html
        import re

        # 移除危险标签
        dangerous_tags = ["script", "iframe", "object", "embed", "form"]
        for tag in dangerous_tags:
            pattern = rf"<{tag}[^>]*>.*?</{tag}>"
            input_str = re.sub(pattern, "", input_str, flags=re.IGNORECASE)

        # HTML转义
        return html.escape(input_str)

    @staticmethod
    def validate_email(email: str) -> bool:
        """验证邮箱格式"""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))


class AuditLogger:
    """审计日志"""

    def __init__(self, db_session=None):
        self.db_session = db_session

    def log_operation(
        self,
        user_id: str,
        operation: str,
        resource: str,
        details: dict[str, Any] = None,
    ):
        """记录操作审计日志"""
        audit_log = {
            "user_id": user_id,
            "operation": operation,
            "resource": resource,
            "details": details or {},
            "timestamp": datetime.utcnow(),
            "ip_address": self.get_client_ip(),
            "user_agent": self.get_user_agent(),
        }

        logger.info(f"Audit Log: {audit_log}")

        # 存储到数据库
        if self.db_session:
            self.save_audit_log(audit_log)

    def get_client_ip(self) -> str:
        """获取客户端IP"""
        # 这里应该从请求上下文获取
        return "unknown"

    def get_user_agent(self) -> str:
        """获取用户代理"""
        # 这里应该从请求上下文获取
        return "unknown"

    def save_audit_log(self, audit_log: dict[str, Any]):
        """保存审计日志到数据库"""
        # 这里应该实现数据库存储逻辑


class SecurityMiddleware:
    """安全中间件"""

    def __init__(self, rate_limiter: RateLimiter):
        self.rate_limiter = rate_limiter

    async def __call__(self, request: Request, call_next):
        """中间件处理"""
        # 获取客户端ID
        client_id = self.rate_limiter.get_client_id(request)

        # 检查限流
        if not self.rate_limiter.is_allowed(client_id):
            raise HTTPException(status_code=429, detail="Too many requests")

        # 处理请求
        response = await call_next(request)

        # 添加安全响应头
        response.headers["X-Content-Type-Options"] = "nosnif"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response
