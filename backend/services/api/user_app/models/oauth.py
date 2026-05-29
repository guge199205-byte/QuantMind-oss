"""
设备管理和密码历史模型
"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, func

from backend.services.api.user_app.models.user import Base


class LoginDevice(Base):
    """登录设备管理表"""

    __tablename__ = "login_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True, comment="用户ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")

    # 设备信息
    device_id = Column(
        String(128), unique=True, nullable=False, index=True, comment="设备唯一ID"
    )
    device_name = Column(String(128), comment="设备名称")
    device_type = Column(String(32), comment="设备类型：mobile/desktop/tablet")
    os = Column(String(64), comment="操作系统")
    browser = Column(String(64), comment="浏览器")

    # 位置信息
    ip_address = Column(String(64), comment="IP地址")
    location = Column(String(128), comment="地理位置")

    # 状态
    is_trusted = Column(Boolean, default=False, comment="是否信任设备")
    is_active = Column(Boolean, default=True, comment="是否活跃")

    # 时间
    first_seen_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at = Column(DateTime(timezone=True), comment="最后活跃时间")
    last_location_change = Column(DateTime(timezone=True), comment="最后位置变化时间")

    def __repr__(self):
        return f"<LoginDevice(user_id={self.user_id}, device_id={self.device_id})>"
