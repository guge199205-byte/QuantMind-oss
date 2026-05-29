from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.services.api.user_app.middleware.auth import require_admin
from backend.services.api.user_app.schemas.user import PaginatedResponse, UserResponse
from backend.services.api.user_app.services.user_service import UserService

router = APIRouter()


def get_user_service() -> UserService:
    return UserService()


@router.get("/")
async def list_users(
    query: str | None = Query(None, description="搜索关键词"),
    is_active: bool | None = Query(None, description="是否激活"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(require_admin),
    user_service: UserService = Depends(get_user_service),
):
    """管理员获取用户列表"""
    tenant_id = current_user.get("tenant_id", "default")

    users, total = await user_service.search_users(
        tenant_id=tenant_id,
        query=query,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    users_list = []
    for user in users:
        # 显式转换，确保在 session 范围内完成
        users_list.append(UserResponse.from_orm(user).dict())

    return {
        "success": True,
        "code": 200,
        "message": "success",
        "data": users_list,
    }



@router.post("/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: str,
    current_user: dict = Depends(require_admin),
    user_service: UserService = Depends(get_user_service),
):
    """切换用户启用/禁用状态"""
    tenant_id = current_user.get("tenant_id", "default")
    user = await user_service.get_user_by_id(user_id, tenant_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    new_status = not user.is_active
    updated_user = await user_service.update_user(user_id, tenant_id, is_active=new_status)

    return {"code": 200, "message": "状态已更新", "data": {"is_active": updated_user.is_active}}
