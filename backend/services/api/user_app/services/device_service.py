"""
设备管理服务
"""

import hashlib
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from user_agents import parse

from backend.services.api.user_app.models.oauth import LoginDevice

logger = logging.getLogger(__name__)


class DeviceService:
    """设备管理服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_device_id(self, user_id: str, user_agent: str, ip_address: str) -> str:
        """
        生成设备唯一ID (User + UA + IP)
        """
        raw = f"{user_id}:{user_agent}:{ip_address}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _parse_user_agent(self, user_agent: str) -> dict:
        """
        解析User-Agent字符串
        """
        ua = parse(user_agent)
        return {
            "device_type": ("mobile" if ua.is_mobile else ("tablet" if ua.is_tablet else "desktop")),
            "os": f"{ua.os.family} {ua.os.version_string}",
            "browser": f"{ua.browser.family} {ua.browser.version_string}",
            "device_name": (f"{ua.device.brand} {ua.device.model}" if ua.device.brand else ua.os.family),
        }

    async def record_device_login(
        self,
        user_id: str,
        tenant_id: str,
        user_agent: str,
        ip_address: str,
        location: str | None = None,
    ) -> LoginDevice:
        """
        记录设备登录

        Args:
            user_id: 用户ID
            user_agent: User-Agent字符串
            ip_address: IP地址
            location: 地理位置（可选）
        """
        device_id = self._generate_device_id(user_id, user_agent, ip_address)
        device_info = self._parse_user_agent(user_agent)

        # 查找已有设备
        stmt = select(LoginDevice).where(
            LoginDevice.device_id == device_id,
            LoginDevice.user_id == user_id,
            LoginDevice.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        device = result.scalar_one_or_none()

        if device:
            # 更新设备信息
            device.last_seen_at = datetime.now()
            device.ip_address = ip_address
            if location and location != device.location:
                device.location = location
                device.last_location_change = datetime.now()
        else:
            # 创建新设备记录
            device = LoginDevice(
                user_id=user_id,
                tenant_id=tenant_id,
                device_id=device_id,
                device_name=device_info["device_name"],
                device_type=device_info["device_type"],
                os=device_info["os"],
                browser=device_info["browser"],
                ip_address=ip_address,
                location=location,
                last_seen_at=datetime.now(),
            )
            self.db.add(device)

        await self.db.commit()
        await self.db.refresh(device)

        return device

    async def get_user_devices(self, user_id: str, tenant_id: str, active_only: bool = False) -> list[LoginDevice]:
        """
        获取用户的所有设备

        Args:
            user_id: 用户ID
            active_only: 是否只返回活跃设备
        """
        stmt = select(LoginDevice).where(
            LoginDevice.user_id == user_id,
            LoginDevice.tenant_id == tenant_id,
        )

        if active_only:
            stmt = stmt.where(LoginDevice.is_active)

        stmt = stmt.order_by(LoginDevice.last_seen_at.desc())

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def trust_device(self, user_id: str, tenant_id: str, device_id: str) -> bool:
        """
        信任设备
        """
        stmt = select(LoginDevice).where(
            LoginDevice.user_id == user_id,
            LoginDevice.tenant_id == tenant_id,
            LoginDevice.device_id == device_id,
        )
        result = await self.db.execute(stmt)
        device = result.scalar_one_or_none()

        if not device:
            raise ValueError("设备不存在")

        device.is_trusted = True
        await self.db.commit()

        return True

    async def untrust_device(self, user_id: str, tenant_id: str, device_id: str) -> bool:
        """
        取消信任设备
        """
        stmt = select(LoginDevice).where(
            LoginDevice.user_id == user_id,
            LoginDevice.tenant_id == tenant_id,
            LoginDevice.device_id == device_id,
        )
        result = await self.db.execute(stmt)
        device = result.scalar_one_or_none()

        if not device:
            raise ValueError("设备不存在")

        device.is_trusted = False
        await self.db.commit()

        return True

    async def remove_device(self, user_id: str, tenant_id: str, device_id: str) -> bool:
        """
        移除设备（标记为不活跃）
        """
        stmt = select(LoginDevice).where(
            LoginDevice.user_id == user_id,
            LoginDevice.tenant_id == tenant_id,
            LoginDevice.device_id == device_id,
        )
        result = await self.db.execute(stmt)
        device = result.scalar_one_or_none()

        if not device:
            raise ValueError("设备不存在")

        device.is_active = False
        await self.db.commit()

        return True

    async def check_suspicious_login(
        self,
        user_id: str,
        tenant_id: str,
        ip_address: str,
        location: str | None = None,
    ) -> dict:
        """
        检查可疑登录

        Returns:
            包含is_suspicious和reason的字典
        """
        # 获取用户最近的登录设备
        devices = await self.get_user_devices(user_id, tenant_id, active_only=True)

        if not devices:
            # 首次登录
            return {
                "is_suspicious": False,
                "reason": "首次登录",
            }

        # 检查IP地址
        recent_ips = {device.ip_address for device in devices[-5:]}
        if ip_address not in recent_ips:
            # 新IP地址
            if location:
                # 检查地理位置变化
                recent_locations = {device.location for device in devices[-5:] if device.location}
                if recent_locations and location not in recent_locations:
                    return {
                        "is_suspicious": True,
                        "reason": "异地登录",
                        "details": f"新位置: {location}",
                    }

            return {
                "is_suspicious": True,
                "reason": "新IP地址",
                "details": f"IP: {ip_address}",
            }

        return {
            "is_suspicious": False,
            "reason": "正常登录",
        }
