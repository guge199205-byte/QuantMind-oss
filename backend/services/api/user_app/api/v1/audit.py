"""
Audit Log API Routes
审计日志查询API路由
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.services.api.user_app.database import get_db
from backend.services.api.user_app.middleware.auth import (
    get_current_user,
    require_permission,
)
from backend.services.api.user_app.services.audit_service import AuditLogService

router = APIRouter(prefix="/audit")


class AuditLogResponse(BaseModel):
    """审计日志响应"""

    id: int
    user_id: str
    action: str
    resource: str | None
    resource_id: str | None
    description: str | None
    ip_address: str | None
    request_method: str | None
    request_path: str | None
    status_code: int | None
    success: bool
    error_message: str | None
    created_at: datetime
    duration_ms: int | None


class ResponseModel(BaseModel):
    """统一响应模型"""

    code: int = 200
    message: str = "success"
    data: dict = {}


@router.get("/my-logs", response_model=ResponseModel)
async def get_my_logs(
    action: str | None = Query(None, description="操作类型"),
    resource: str | None = Query(None, description="资源类型"),
    success: bool | None = Query(None, description="是否成功"),
    limit: int = Query(50, ge=1, le=200, description="数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    获取当前用户的操作日志
    """
    audit_service = AuditLogService(db)

    logs, total = await audit_service.get_user_logs(
        user_id=current_user["user_id"],
        tenant_id=current_user["tenant_id"],
        action=action,
        resource=resource,
        success=success,
        limit=limit,
        offset=offset,
    )

    return {
        "code": 200,
        "message": "success",
        "data": {
            "logs": [
                {
                    "id": log.id,
                    "action": log.action,
                    "resource": log.resource,
                    "resource_id": log.resource_id,
                    "description": log.description,
                    "ip_address": log.ip_address,
                    "request_method": log.request_method,
                    "request_path": log.request_path,
                    "status_code": log.status_code,
                    "success": log.success,
                    "error_message": log.error_message,
                    "created_at": log.created_at.isoformat(),
                    "duration_ms": log.duration_ms,
                }
                for log in logs
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/my-statistics", response_model=ResponseModel)
async def get_my_statistics(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """
    获取当前用户的操作统计
    """
    audit_service = AuditLogService(db)

    stats = await audit_service.get_action_statistics(
        tenant_id=current_user["tenant_id"],
        user_id=current_user["user_id"],
    )

    return {"code": 200, "message": "success", "data": stats}


@router.get("/users/{user_id}/logs", response_model=ResponseModel)
async def get_user_logs(
    user_id: str,
    action: str | None = Query(None, description="操作类型"),
    resource: str | None = Query(None, description="资源类型"),
    success: bool | None = Query(None, description="是否成功"),
    limit: int = Query(50, ge=1, le=200, description="数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: dict = Depends(require_permission("system.audit")),
    db=Depends(get_db),
):
    """
    获取指定用户的操作日志（需要system.audit权限）
    """
    audit_service = AuditLogService(db)

    logs, total = await audit_service.get_user_logs(
        user_id=user_id,
        tenant_id=current_user["tenant_id"],
        action=action,
        resource=resource,
        success=success,
        limit=limit,
        offset=offset,
    )

    return {
        "code": 200,
        "message": "success",
        "data": {
            "logs": [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "action": log.action,
                    "resource": log.resource,
                    "resource_id": log.resource_id,
                    "description": log.description,
                    "ip_address": log.ip_address,
                    "request_method": log.request_method,
                    "request_path": log.request_path,
                    "status_code": log.status_code,
                    "success": log.success,
                    "error_message": log.error_message,
                    "created_at": log.created_at.isoformat(),
                    "duration_ms": log.duration_ms,
                }
                for log in logs
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/recent", response_model=ResponseModel)
async def get_recent_logs(
    limit: int = Query(100, ge=1, le=500, description="数量限制"),
    action: str | None = Query(None, description="操作类型"),
    resource: str | None = Query(None, description="资源类型"),
    current_user: dict = Depends(require_permission("system.audit")),
    db=Depends(get_db),
):
    """
    获取最近的操作日志（需要system.audit权限）
    """
    audit_service = AuditLogService(db)

    logs = await audit_service.get_recent_logs(
        tenant_id=current_user["tenant_id"],
        limit=limit,
        action=action,
        resource=resource,
    )

    return {
        "code": 200,
        "message": "success",
        "data": {
            "logs": [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "action": log.action,
                    "resource": log.resource,
                    "resource_id": log.resource_id,
                    "description": log.description,
                    "ip_address": log.ip_address,
                    "success": log.success,
                    "created_at": log.created_at.isoformat(),
                    "duration_ms": log.duration_ms,
                }
                for log in logs
            ],
            "count": len(logs),
        },
    }


@router.get("/failed", response_model=ResponseModel)
async def get_failed_actions(
    limit: int = Query(100, ge=1, le=500, description="数量限制"),
    current_user: dict = Depends(require_permission("system.audit")),
    db=Depends(get_db),
):
    """
    获取失败的操作（需要system.audit权限）
    """
    audit_service = AuditLogService(db)

    logs = await audit_service.get_failed_actions(
        tenant_id=current_user["tenant_id"],
        limit=limit,
    )

    return {
        "code": 200,
        "message": "success",
        "data": {
            "logs": [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "action": log.action,
                    "resource": log.resource,
                    "error_message": log.error_message,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at.isoformat(),
                }
                for log in logs
            ],
            "count": len(logs),
        },
    }


@router.get("/statistics", response_model=ResponseModel)
async def get_overall_statistics(current_user: dict = Depends(require_permission("system.audit")), db=Depends(get_db)):
    """
    获取整体操作统计（需要system.audit权限）
    """
    audit_service = AuditLogService(db)

    stats = await audit_service.get_action_statistics(tenant_id=current_user["tenant_id"])

    return {"code": 200, "message": "success", "data": stats}
