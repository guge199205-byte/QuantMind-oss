"""
RBAC Management API Routes
角色权限管理API路由
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.services.api.user_app.database import get_db
from backend.services.api.user_app.middleware.auth import (
    get_current_user,
    require_permission,
)
from backend.services.api.user_app.services.rbac_service import RBACService

router = APIRouter(prefix="/rbac")


class RoleResponse(BaseModel):
    """角色响应"""

    id: int
    name: str
    code: str
    description: str | None
    is_active: bool
    priority: int


class PermissionResponse(BaseModel):
    """权限响应"""

    id: int
    name: str
    code: str
    resource: str
    action: str
    description: str | None


class ResponseModel(BaseModel):
    """统一响应模型"""

    code: int = 200
    message: str = "success"
    data: dict = {}


@router.get("/user/roles", response_model=ResponseModel)
async def get_user_roles(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """
    获取当前用户的角色
    """
    rbac_service = RBACService(db)
    roles = await rbac_service.get_user_roles(current_user["user_id"])

    return {
        "code": 200,
        "message": "success",
        "data": {
            "roles": [
                {
                    "id": role.id,
                    "name": role.name,
                    "code": role.code,
                    "description": role.description,
                    "priority": role.priority,
                }
                for role in roles
            ]
        },
    }


@router.get("/user/permissions", response_model=ResponseModel)
async def get_user_permissions(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """
    获取当前用户的所有权限
    """
    rbac_service = RBACService(db)
    permissions = await rbac_service.get_user_permissions(current_user["user_id"])

    return {
        "code": 200,
        "message": "success",
        "data": {"permissions": list(permissions), "count": len(permissions)},
    }


@router.get("/check-permission", response_model=ResponseModel)
async def check_permission(
    permission_code: str = Query(..., description="权限代码"),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    检查用户是否拥有特定权限
    """
    rbac_service = RBACService(db)
    has_perm = await rbac_service.has_permission(current_user["user_id"], permission_code)

    return {
        "code": 200,
        "message": "success",
        "data": {"has_permission": has_perm, "permission_code": permission_code},
    }


@router.post("/users/{user_id}/roles/{role_id}", response_model=ResponseModel)
async def add_role_to_user(
    user_id: str,
    role_id: int,
    current_user: dict = Depends(require_permission("user.update")),
    db=Depends(get_db),
):
    """
    给用户添加角色（需要user.update权限）
    """
    rbac_service = RBACService(db)

    try:
        await rbac_service.add_role_to_user(user_id, role_id)

        return {"code": 200, "message": "角色添加成功", "data": {}}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/users/{user_id}/roles/{role_id}", response_model=ResponseModel)
async def remove_role_from_user(
    user_id: str,
    role_id: int,
    current_user: dict = Depends(require_permission("user.update")),
    db=Depends(get_db),
):
    """
    移除用户的角色（需要user.update权限）
    """
    rbac_service = RBACService(db)

    try:
        await rbac_service.remove_role_from_user(user_id, role_id)

        return {"code": 200, "message": "角色移除成功", "data": {}}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/roles", response_model=ResponseModel)
async def list_roles(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """
    获取所有角色列表
    """
    from sqlalchemy import select

    from backend.services.api.user_app.models.rbac import Role

    stmt = select(Role).where(Role.is_active).order_by(Role.priority.desc())
    result = await db.execute(stmt)
    roles = result.scalars().all()

    return {
        "code": 200,
        "message": "success",
        "data": {
            "roles": [
                {
                    "id": role.id,
                    "name": role.name,
                    "code": role.code,
                    "description": role.description,
                    "priority": role.priority,
                    "is_system": role.is_system,
                }
                for role in roles
            ],
            "count": len(roles),
        },
    }


@router.get("/permissions", response_model=ResponseModel)
async def list_permissions(
    resource: str | None = Query(None, description="资源类型"),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    获取所有权限列表
    """
    from sqlalchemy import select

    from backend.services.api.user_app.models.rbac import Permission

    stmt = select(Permission).where(Permission.is_active)

    if resource:
        stmt = stmt.where(Permission.resource == resource)

    result = await db.execute(stmt)
    permissions = result.scalars().all()

    return {
        "code": 200,
        "message": "success",
        "data": {
            "permissions": [
                {
                    "id": perm.id,
                    "name": perm.name,
                    "code": perm.code,
                    "resource": perm.resource,
                    "action": perm.action,
                    "description": perm.description,
                }
                for perm in permissions
            ],
            "count": len(permissions),
        },
    }
