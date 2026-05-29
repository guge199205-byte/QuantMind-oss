"""
Audit Log Service
审计日志服务
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.user_app.models.rbac import UserAuditLog

logger = logging.getLogger(__name__)


class AuditLogService:
    """审计日志服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_action(
        self,
        user_id: str,
        tenant_id: str,
        action: str,
        resource: str | None = None,
        resource_id: str | None = None,
        description: str | None = None,
        request_data: dict | None = None,
        response_data: dict | None = None,
        request: Request | None = None,
        status_code: int = 200,
        success: bool = True,
        error_message: str | None = None,
        duration_ms: int | None = None,
    ):
        """
        记录用户操作

        Args:
            user_id: 用户ID
            action: 操作类型 (login/logout/create/update/delete等)
            resource: 资源类型 (user/strategy/portfolio/order等)
            resource_id: 资源ID
            description: 操作描述
            request_data: 请求数据
            response_data: 响应数据
            request: FastAPI Request对象
            status_code: HTTP状态码
            success: 是否成功
            error_message: 错误信息
            duration_ms: 处理时长(毫秒)
        """
        try:
            # 提取请求信息
            ip_address = None
            user_agent = None
            request_method = None
            request_path = None

            if request:
                ip_address = self._get_client_ip(request)
                user_agent = request.headers.get("user-agent")
                request_method = request.method
                request_path = str(request.url.path)

            # 序列化数据
            request_data_json = json.dumps(request_data) if request_data else None
            response_data_json = json.dumps(response_data) if response_data else None

            # 创建日志记录
            log_entry = UserAuditLog(
                user_id=user_id,
                tenant_id=tenant_id,
                action=action,
                resource=resource,
                resource_id=resource_id,
                description=description,
                request_data=request_data_json,
                response_data=response_data_json,
                ip_address=ip_address,
                user_agent=user_agent,
                request_method=request_method,
                request_path=request_path,
                status_code=status_code,
                success=success,
                error_message=error_message,
                duration_ms=duration_ms,
            )

            self.db.add(log_entry)
            await self.db.commit()

            logger.info(f"📝 审计日志: user={user_id}, action={action}, " f"resource={resource}, success={success}")

        except Exception as e:
            logger.error(f"❌ 记录审计日志失败: {e}")
            # 不影响主流程，仅记录错误

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP地址"""
        # 尝试从X-Forwarded-For获取
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # 尝试从X-Real-IP获取
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # 使用client地址
        if request.client:
            return request.client.host

        return "unknown"

    async def get_user_logs(
        self,
        user_id: str,
        tenant_id: str,
        action: str | None = None,
        resource: str | None = None,
        success: bool | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[UserAuditLog], int]:
        """
        查询用户日志

        Returns:
            (logs, total_count)
        """
        # 构建查询
        stmt = select(UserAuditLog).where(
            UserAuditLog.user_id == user_id,
            UserAuditLog.tenant_id == tenant_id,
        )

        # 添加过滤条件
        if action:
            stmt = stmt.where(UserAuditLog.action == action)

        if resource:
            stmt = stmt.where(UserAuditLog.resource == resource)

        if success is not None:
            stmt = stmt.where(UserAuditLog.success == success)

        if start_date:
            stmt = stmt.where(UserAuditLog.created_at >= start_date)

        if end_date:
            stmt = stmt.where(UserAuditLog.created_at <= end_date)

        # 排序和分页
        stmt = stmt.order_by(desc(UserAuditLog.created_at))

        # 获取总数
        count_stmt = select(UserAuditLog).where(
            UserAuditLog.user_id == user_id,
            UserAuditLog.tenant_id == tenant_id,
        )
        if action:
            count_stmt = count_stmt.where(UserAuditLog.action == action)
        if resource:
            count_stmt = count_stmt.where(UserAuditLog.resource == resource)
        if success is not None:
            count_stmt = count_stmt.where(UserAuditLog.success == success)
        if start_date:
            count_stmt = count_stmt.where(UserAuditLog.created_at >= start_date)
        if end_date:
            count_stmt = count_stmt.where(UserAuditLog.created_at <= end_date)

        count_result = await self.db.execute(count_stmt)
        total = len(count_result.scalars().all())

        # 获取数据
        stmt = stmt.limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        logs = result.scalars().all()

        return logs, total

    async def get_recent_logs(
        self,
        tenant_id: str,
        limit: int = 100,
        action: str | None = None,
        resource: str | None = None,
    ) -> list[UserAuditLog]:
        """获取最近的日志"""
        stmt = select(UserAuditLog).where(UserAuditLog.tenant_id == tenant_id).order_by(desc(UserAuditLog.created_at))

        if action:
            stmt = stmt.where(UserAuditLog.action == action)

        if resource:
            stmt = stmt.where(UserAuditLog.resource == resource)

        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_failed_actions(
        self, tenant_id: str, user_id: str | None = None, limit: int = 100
    ) -> list[UserAuditLog]:
        """获取失败的操作"""
        stmt = (
            select(UserAuditLog)
            .where(
                not UserAuditLog.success,
                UserAuditLog.tenant_id == tenant_id,
            )
            .order_by(desc(UserAuditLog.created_at))
        )

        if user_id:
            stmt = stmt.where(UserAuditLog.user_id == user_id)

        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_action_statistics(
        self,
        tenant_id: str,
        user_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        获取操作统计

        Returns:
            {
                "total_actions": 100,
                "success_rate": 0.95,
                "action_counts": {"login": 20, "create": 30, ...},
                "resource_counts": {"user": 10, "strategy": 20, ...}
            }
        """
        # 构建基础查询
        base_stmt = select(UserAuditLog).where(UserAuditLog.tenant_id == tenant_id)

        if user_id:
            base_stmt = base_stmt.where(UserAuditLog.user_id == user_id)

        if start_date:
            base_stmt = base_stmt.where(UserAuditLog.created_at >= start_date)

        if end_date:
            base_stmt = base_stmt.where(UserAuditLog.created_at <= end_date)

        # 获取所有日志
        result = await self.db.execute(base_stmt)
        logs = result.scalars().all()

        if not logs:
            return {
                "total_actions": 0,
                "success_rate": 0,
                "action_counts": {},
                "resource_counts": {},
            }

        # 统计
        total_actions = len(logs)
        success_count = sum(1 for log in logs if log.success)
        success_rate = success_count / total_actions if total_actions > 0 else 0

        # 按action统计
        action_counts = {}
        for log in logs:
            action_counts[log.action] = action_counts.get(log.action, 0) + 1

        # 按resource统计
        resource_counts = {}
        for log in logs:
            if log.resource:
                resource_counts[log.resource] = resource_counts.get(log.resource, 0) + 1

        return {
            "total_actions": total_actions,
            "success_count": success_count,
            "failed_count": total_actions - success_count,
            "success_rate": round(success_rate, 4),
            "action_counts": action_counts,
            "resource_counts": resource_counts,
        }


# 审计日志装饰器
def audit_log(action: str, resource: str | None = None, description: str | None = None):
    """
    审计日志装饰器

    用法:
    @router.post("/orders")
    @audit_log(action="order.create", resource="order")
    async def create_order(...):
        ...
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 获取参数
            request = kwargs.get("request")
            current_user = kwargs.get("current_user")
            db = kwargs.get("db")

            if not all([request, current_user, db]):
                # 参数不全，直接执行
                return await func(*args, **kwargs)

            start_time = datetime.now()

            try:
                # 执行函数
                result = await func(*args, **kwargs)

                # 计算耗时
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                # 记录审计日志
                audit_service = AuditLogService(db)
                await audit_service.log_action(
                    user_id=current_user["user_id"],
                    tenant_id=current_user["tenant_id"],
                    action=action,
                    resource=resource,
                    description=description,
                    request=request,
                    status_code=200,
                    success=True,
                    duration_ms=duration_ms,
                )

                return result

            except Exception as e:
                # 计算耗时
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                # 记录失败日志
                audit_service = AuditLogService(db)
                await audit_service.log_action(
                    user_id=current_user.get("user_id", "unknown"),
                    tenant_id=current_user.get("tenant_id", "unknown"),
                    action=action,
                    resource=resource,
                    description=description,
                    request=request,
                    status_code=500,
                    success=False,
                    error_message=str(e),
                    duration_ms=duration_ms,
                )

                raise

        return wrapper

    return decorator
