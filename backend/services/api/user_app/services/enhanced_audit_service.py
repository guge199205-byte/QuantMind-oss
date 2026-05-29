"""
增强的审计日志服务
"""

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.user_app.models.rbac import UserAuditLog

logger = logging.getLogger(__name__)


class EnhancedAuditService:
    """增强的审计日志服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_operation(
        self,
        user_id: str,
        tenant_id: str,
        action: str,
        resource: str,
        resource_id: str | None = None,
        description: str | None = None,
        request_data: dict | None = None,
        response_data: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_method: str | None = None,
        request_path: str | None = None,
        status_code: int | None = None,
        success: bool = True,
        error_message: str | None = None,
        duration_ms: int | None = None,
    ) -> UserAuditLog:
        """
        记录用户操作审计日志

        Args:
            user_id: 用户ID
            action: 操作类型（如：login, create, update, delete）
            resource: 资源类型（如：user, order, strategy）
            resource_id: 资源ID
            description: 操作描述
            request_data: 请求数据
            response_data: 响应数据
            ip_address: IP地址
            user_agent: User-Agent
            request_method: 请求方法
            request_path: 请求路径
            status_code: 状态码
            success: 是否成功
            error_message: 错误信息
            duration_ms: 处理时长（毫秒）
        """
        audit_log = UserAuditLog(
            user_id=user_id,
            tenant_id=tenant_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            description=description,
            request_data=(json.dumps(request_data, ensure_ascii=False) if request_data else None),
            response_data=(json.dumps(response_data, ensure_ascii=False) if response_data else None),
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            request_path=request_path,
            status_code=status_code,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
        )

        self.db.add(audit_log)
        try:
            await self.db.commit()
        except Exception as exc:  # 审计不可用时不阻断主流程
            await self.db.rollback()
            logger.warning(
                "Audit log persist failed, ignored",
                extra={"user_id": user_id, "action": action, "error": str(exc)},
            )
            return audit_log
        else:
            logger.info(
                f"Audit: user={user_id} action={action} resource={resource} "
                f"success={success} duration={duration_ms}ms"
            )
            return audit_log

    async def log_login(
        self,
        user_id: str,
        tenant_id: str,
        success: bool,
        ip_address: str,
        user_agent: str,
        error_message: str | None = None,
    ) -> UserAuditLog:
        """记录登录操作"""
        return await self.log_operation(
            user_id=user_id,
            tenant_id=tenant_id,
            action="login",
            resource="auth",
            description=f"用户{'成功' if success else '失败'}登录",
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )

    async def log_logout(
        self,
        user_id: str,
        tenant_id: str,
        ip_address: str,
        user_agent: str,
    ) -> UserAuditLog:
        """记录登出操作"""
        return await self.log_operation(
            user_id=user_id,
            tenant_id=tenant_id,
            action="logout",
            resource="auth",
            description="用户登出",
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_password_change(
        self,
        user_id: str,
        tenant_id: str,
        ip_address: str,
        user_agent: str,
        success: bool,
    ) -> UserAuditLog:
        """记录密码修改"""
        return await self.log_operation(
            user_id=user_id,
            tenant_id=tenant_id,
            action="password_change",
            resource="user",
            description="修改密码",
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
        )

    async def get_user_audit_logs(
        self,
        user_id: str,
        tenant_id: str,
        action: str | None = None,
        resource: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UserAuditLog]:
        """
        获取用户的审计日志

        Args:
            user_id: 用户ID
            action: 操作类型过滤
            resource: 资源类型过滤
            limit: 返回数量限制
            offset: 偏移量
        """
        stmt = select(UserAuditLog).where(
            UserAuditLog.user_id == user_id,
            UserAuditLog.tenant_id == tenant_id,
        )

        if action:
            stmt = stmt.where(UserAuditLog.action == action)

        if resource:
            stmt = stmt.where(UserAuditLog.resource == resource)

        stmt = stmt.order_by(UserAuditLog.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_recent_logins(self, user_id: str, tenant_id: str, limit: int = 10) -> list[UserAuditLog]:
        """获取最近的登录记录"""
        return await self.get_user_audit_logs(
            user_id=user_id,
            tenant_id=tenant_id,
            action="login",
            limit=limit,
        )

    async def detect_anomalies(self, user_id: str, tenant_id: str) -> dict[str, Any]:
        """
        检测异常行为

        Returns:
            包含异常信息的字典
        """
        # 获取最近100条操作记录
        logs = await self.get_user_audit_logs(user_id, tenant_id, limit=100)

        if not logs:
            return {"has_anomaly": False}

        anomalies = []

        # 检测失败登录次数
        recent_failed_logins = [log for log in logs[:20] if log.action == "login" and not log.success]
        if len(recent_failed_logins) > 5:
            anomalies.append(
                {
                    "type": "multiple_failed_logins",
                    "count": len(recent_failed_logins),
                    "description": "检测到多次登录失败",
                }
            )

        # 检测异常IP
        ip_addresses = [log.ip_address for log in logs if log.ip_address]
        if len(set(ip_addresses)) > 10:
            anomalies.append(
                {
                    "type": "multiple_ips",
                    "count": len(set(ip_addresses)),
                    "description": "检测到多个不同IP地址",
                }
            )

        return {
            "has_anomaly": len(anomalies) > 0,
            "anomalies": anomalies,
        }
