"""
User API Routes
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from backend.services.api.user_app.middleware.auth import (
    get_current_user,
    require_admin,
)
from backend.services.api.user_app.schemas.user import (
    PaginatedResponse,
    PhoneBindRequest,
    PhoneChangeRequest,
    PhoneSendCodeRequest,
    ResponseModel,
    UserProfileUpdate,
    UserResponse,
)
from backend.services.api.user_app.services.audit_service import AuditLogService
from backend.services.api.user_app.services.profile_service import ProfileService
from backend.services.api.user_app.services.user_service import UserService

router = APIRouter(prefix="/users")


def get_user_service() -> UserService:
    """获取用户服务"""
    return UserService()


def get_profile_service() -> ProfileService:
    return ProfileService()


def _parse_date(date_str: str | None, is_end: bool = False) -> datetime | None:
    if not date_str:
        return None
    try:
        if len(date_str) == 10:
            dt = datetime.fromisoformat(date_str)
            if is_end:
                return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            return dt
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效日期格式: {date_str}")


def _derive_login_type(request_path: str | None) -> str:
    path = (request_path or "").lower()
    if "mfa" in path:
        return "mfa"
    if "sso" in path:
        return "sso"
    return "password"


def _device_type_and_name(user_agent: str | None) -> tuple[str, str]:
    ua = (user_agent or "").lower()
    if any(k in ua for k in ("iphone", "android", "mobile", "harmony")):
        return "mobile", "移动设备"
    if "ipad" in ua or "tablet" in ua:
        return "tablet", "平板设备"
    if ua:
        return "desktop", "桌面设备"
    return "unknown", "未知设备"


@router.get("/", response_model=PaginatedResponse)
async def list_users(
    query: str | None = Query(None, description="搜索关键词"),
    is_active: bool | None = Query(None, description="是否激活"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(require_admin),
    user_service: UserService = Depends(get_user_service),
):
    """
    获取用户列表（需要管理员权限）

    - **query**: 搜索用户名或邮箱
    - **is_active**: 筛选激活状态
    - **page**: 页码（从1开始）
    - **page_size**: 每页数量（1-100）
    """
    users, total = await user_service.search_users(
        tenant_id=current_user["tenant_id"],
        query=query,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    return {
        "code": 200,
        "message": "success",
        "data": {
            "items": [UserResponse.from_orm(user).dict() for user in users],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        },
    }


@router.get("/me", response_model=ResponseModel)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """
    获取当前登录用户信息
    """
    user = await user_service.get_user_by_id(
        current_user["user_id"], current_user["tenant_id"]
    )

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return {
        "code": 200,
        "message": "success",
        "data": {
            **UserResponse.from_orm(user).dict(),
            "is_admin": current_user.get("is_admin", False),
        },
    }


@router.post("/me/phone/send-code", response_model=ResponseModel)
async def send_phone_manage_code(
    payload: PhoneSendCodeRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    个人中心：发送绑定/换绑手机号验证码（需要登录）。
    OSS版本不支持短信验证。
    """
    raise HTTPException(status_code=503, detail="OSS版本不支持短信验证功能")


@router.post("/me/phone/bind", response_model=ResponseModel)
async def bind_phone(
    payload: PhoneBindRequest,
    current_user: dict = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service),
):
    """
    个人中心：绑定手机号（需要登录）。
    OSS版本不支持短信验证。
    """
    raise HTTPException(status_code=503, detail="OSS版本不支持短信验证功能")


@router.post("/me/phone/change", response_model=ResponseModel)
async def change_phone(
    payload: PhoneChangeRequest,
    current_user: dict = Depends(get_current_user),
    profile_service: ProfileService = Depends(get_profile_service),
):
    """
    个人中心：换绑手机号（需要登录）。
    OSS版本不支持短信验证。
    """
    raise HTTPException(status_code=503, detail="OSS版本不支持短信验证功能")


@router.get("/{user_id}", response_model=ResponseModel)
async def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """
    获取指定用户信息

    - **user_id**: 用户ID
    """
    # 检查权限：只能查看自己的信息（除非是管理员）
    if user_id != current_user["user_id"] and not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该用户信息"
        )

    user = await user_service.get_user_by_id(user_id, current_user["tenant_id"])

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return {
        "code": 200,
        "message": "success",
        "data": {
            **UserResponse.from_orm(user).dict(),
            "is_admin": current_user.get("is_admin", False),
        },
    }


@router.get("/{user_id}/detail", response_model=ResponseModel)
async def get_user_detail(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """
    获取用户详细信息（包含档案）

    - **user_id**: 用户ID
    """
    # 检查权限
    if user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该用户信息"
        )

    user_detail = await user_service.get_user_detail(user_id, current_user["tenant_id"])

    if not user_detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return {"code": 200, "message": "success", "data": user_detail.dict()}


@router.get("/{user_id}/login-history", response_model=ResponseModel)
async def get_login_history(
    user_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    success: bool | None = Query(None, description="登录是否成功"),
    login_type: str | None = Query(None, description="登录类型: password/mfa/sso"),
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
):
    """
    获取登录历史（仅本人或管理员可查看）。
    """
    if user_id != current_user["user_id"] and not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该用户登录历史"
        )

    allowed_types = {"password", "mfa", "sso"}
    if login_type and login_type not in allowed_types:
        raise HTTPException(status_code=400, detail="无效登录类型")

    start_dt = _parse_date(start_date, is_end=False)
    end_dt = _parse_date(end_date, is_end=True)
    offset = (page - 1) * page_size
    tenant_id = current_user["tenant_id"]

    from backend.shared.database_manager_v2 import get_session

    async with get_session(read_only=True) as session:
        audit_service = AuditLogService(session)

        if login_type:
            logs, _ = await audit_service.get_user_logs(
                user_id=user_id,
                tenant_id=tenant_id,
                action="login",
                success=success,
                start_date=start_dt,
                end_date=end_dt,
                limit=5000,
                offset=0,
            )
            filtered_logs = [
                log
                for log in logs
                if _derive_login_type(log.request_path) == login_type
            ]
            total = len(filtered_logs)
            page_logs = filtered_logs[offset : offset + page_size]
        else:
            page_logs, total = await audit_service.get_user_logs(
                user_id=user_id,
                tenant_id=tenant_id,
                action="login",
                success=success,
                start_date=start_dt,
                end_date=end_dt,
                limit=page_size,
                offset=offset,
            )

    history = []
    for log in page_logs:
        device_type, device_name = _device_type_and_name(log.user_agent)
        history.append(
            {
                "id": log.id,
                "user_id": log.user_id,
                "login_type": _derive_login_type(log.request_path),
                "success": bool(log.success),
                "ip_address": log.ip_address or "",
                "location": None,
                "device_type": device_type,
                "device_name": device_name,
                "user_agent": log.user_agent or "",
                "failure_reason": log.error_message,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
        )

    return {
        "code": 200,
        "message": "success",
        "data": {
            "history": history,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if total else 0,
            },
        },
    }


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: dict = Depends(require_admin),
    user_service: UserService = Depends(get_user_service),
):
    """
    删除用户（软删除，需要管理员权限）

    - **user_id**: 用户ID
    """
    success = await user_service.soft_delete_user(user_id, current_user["tenant_id"])

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    return None
