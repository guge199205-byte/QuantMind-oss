"""
设备管理API路由
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from backend.services.api.user_app.middleware.auth import get_current_user
from backend.services.api.user_app.services.device_service import DeviceService
from backend.shared.database_manager_v2 import get_session


class DeviceResponse(BaseModel):
    """设备响应"""

    model_config = ConfigDict(from_attributes=True)

    device_id: str
    device_name: str
    device_type: str
    os: str
    browser: str
    ip_address: str
    location: str = None
    is_trusted: bool
    is_active: bool
    first_seen_at: str
    last_seen_at: str = None


class DeviceTrustRequest(BaseModel):
    """信任设备请求"""

    device_id: str


router = APIRouter(prefix="/devices", tags=["设备管理"])


@router.get("", response_model=list[DeviceResponse])
async def get_my_devices(
    active_only: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """
    获取我的设备列表

    - **active_only**: 是否只返回活跃设备
    """
    async with get_session(read_only=True) as session:
        device_service = DeviceService(session)
        devices = await device_service.get_user_devices(
            user_id=current_user["user_id"],
            tenant_id=current_user["tenant_id"],
            active_only=active_only,
        )

    return [DeviceResponse.from_orm(device) for device in devices]


@router.post("/trust")
async def trust_device(
    request: DeviceTrustRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    信任设备

    - **device_id**: 设备ID
    """
    try:
        async with get_session(read_only=False) as session:
            device_service = DeviceService(session)
            await device_service.trust_device(
                user_id=current_user["user_id"],
                tenant_id=current_user["tenant_id"],
                device_id=request.device_id,
            )

        return {
            "code": 200,
            "message": "设备已信任",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/untrust")
async def untrust_device(
    request: DeviceTrustRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    取消信任设备

    - **device_id**: 设备ID
    """
    try:
        async with get_session(read_only=False) as session:
            device_service = DeviceService(session)
            await device_service.untrust_device(
                user_id=current_user["user_id"],
                tenant_id=current_user["tenant_id"],
                device_id=request.device_id,
            )

        return {
            "code": 200,
            "message": "已取消信任",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{device_id}")
async def remove_device(
    device_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    移除设备

    - **device_id**: 设备ID
    """
    try:
        async with get_session(read_only=False) as session:
            device_service = DeviceService(session)
            await device_service.remove_device(
                user_id=current_user["user_id"],
                tenant_id=current_user["tenant_id"],
                device_id=device_id,
            )

        return {
            "code": 200,
            "message": "设备已移除",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
