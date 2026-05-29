"""
Role-Based Access Control (RBAC) Models
角色权限控制模型
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.services.api.user_app.models.user import Base

# 用户-角色关联表
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(64), ForeignKey("users.user_id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)


# 角色-权限关联表
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)


class Role(Base):
    """角色表"""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, comment="角色名称")
    code = Column(
        String(64), unique=True, nullable=False, index=True, comment="角色代码"
    )
    description = Column(Text, comment="角色描述")

    # 状态
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_system = Column(Boolean, default=False, comment="是否系统角色")

    # 优先级（数字越大权限越高）
    priority = Column(Integer, default=0, comment="优先级")

    # 审计字段
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    permissions = relationship(
        "Permission", secondary=role_permissions, back_populates="roles"
    )

    def __repr__(self):
        return f"<Role(code={self.code}, name={self.name})>"


class Permission(Base):
    """权限表"""

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False, comment="权限名称")
    code = Column(
        String(128), unique=True, nullable=False, index=True, comment="权限代码"
    )
    resource = Column(String(64), nullable=False, index=True, comment="资源类型")
    action = Column(String(32), nullable=False, comment="操作类型")
    description = Column(Text, comment="权限描述")

    # 状态
    is_active = Column(Boolean, default=True, comment="是否激活")

    # 审计字段
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    roles = relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )

    def __repr__(self):
        return f"<Permission(code={self.code}, resource={self.resource}, action={self.action})>"


class UserAuditLog(Base):
    """用户操作审计日志"""

    __tablename__ = "user_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")

    # 操作信息
    action = Column(String(64), nullable=False, index=True, comment="操作类型")
    resource = Column(String(128), comment="操作资源")
    resource_id = Column(String(128), comment="资源ID")

    # 详细信息
    description = Column(Text, comment="操作描述")
    request_data = Column(Text, comment="请求数据(JSON)")
    response_data = Column(Text, comment="响应数据(JSON)")

    # 请求信息
    ip_address = Column(String(64), comment="IP地址")
    user_agent = Column(Text, comment="User Agent")
    request_method = Column(String(16), comment="请求方法")
    request_path = Column(String(255), comment="请求路径")

    # 结果
    status_code = Column(Integer, comment="状态码")
    success = Column(Boolean, default=True, comment="是否成功")
    error_message = Column(Text, comment="错误信息")

    # 时间
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    duration_ms = Column(Integer, comment="处理时长(毫秒)")

    def __repr__(self):
        return f"<UserAuditLog(user_id={self.user_id}, action={self.action})>"


class EmailVerification(Base):
    """邮箱验证表"""

    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False,
                     index=True, comment="用户ID或注册标识")
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    email = Column(String(255), nullable=False, index=True)

    # 验证信息
    verification_code = Column(String(128), unique=True, nullable=False, index=True)
    code_type = Column(
        String(32), nullable=False, comment="类型: register/reset_password/change_email"
    )

    # 状态
    is_used = Column(Boolean, default=False, index=True)
    is_expired = Column(Boolean, default=False)

    # 时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True))

    # 安全
    attempts = Column(Integer, default=0, comment="验证尝试次数")
    ip_address = Column(String(64))

    def __repr__(self):
        return (
            f"<EmailVerification(user_id={self.user_id}, code_type={self.code_type})>"
        )


class PasswordResetToken(Base):
    """密码重置令牌表"""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        String(64), ForeignKey("users.user_id"), nullable=False, index=True
    )
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")
    email = Column(String(255), nullable=False, index=True)

    # 令牌信息
    token = Column(String(128), unique=True, nullable=False, index=True)

    # 状态
    is_used = Column(Boolean, default=False, index=True)
    is_expired = Column(Boolean, default=False)

    # 时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True))

    # 安全
    ip_address = Column(String(64))
    attempts = Column(Integer, default=0, comment="使用尝试次数")

    def __repr__(self):
        return (
            f"<PasswordResetToken(user_id={self.user_id}, token={self.token[:10]}...)>"
        )
