"""
Role-Based Access Control Service
角色权限控制服务
"""

from typing import List, Optional, Set

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.user_app.models.rbac import (
    Permission,
    Role,
    role_permissions,
    user_roles,
)
from backend.services.api.user_app.services.cache_service import CacheService


class RBACService:
    """RBAC服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.cache = CacheService()

    async def get_user_roles(self, user_id: str) -> list[Role]:
        """获取用户的所有角色"""
        # 从数据库查询 (暂时不缓存完整对象，由权限层面处理缓存)
        stmt = (
            select(Role)
            .join(user_roles)
            .where(user_roles.c.user_id == user_id)
            .where(Role.is_active == True)
            .order_by(Role.priority.desc())
        )
        result = await self.db.execute(stmt)
        roles = result.scalars().all()
        return roles

    async def get_user_permissions(self, user_id: str) -> set[str]:
        """获取用户的所有权限代码"""
        # 先从缓存获取
        cache_key = f"user:permissions:{user_id}"
        cached = self.cache.get_json(cache_key)
        if cached is not None:
            return set(cached)

        # 获取用户角色
        roles = await self.get_user_roles(user_id)
        if not roles:
            return set()

        # 获取角色的所有权限
        role_ids = [role.id for role in roles]
        stmt = (
            select(Permission)
            .join(role_permissions)
            .where(role_permissions.c.role_id.in_(role_ids))
            .where(Permission.is_active == True)
        )
        result = await self.db.execute(stmt)
        permissions = result.scalars().all()

        # 提取权限代码
        permission_codes = {perm.code for perm in permissions}

        # 缓存结果（10分钟）
        self.cache.set_json(cache_key, list(permission_codes), ttl=600)

        return permission_codes

    async def has_permission(self, user_id: str, permission_code: str) -> bool:
        """检查用户是否有特定权限"""
        permissions = await self.get_user_permissions(user_id)
        return permission_code in permissions

    async def has_any_permission(self, user_id: str, permission_codes: list[str]) -> bool:
        """检查用户是否有任意一个权限"""
        permissions = await self.get_user_permissions(user_id)
        return any(code in permissions for code in permission_codes)

    async def has_all_permissions(self, user_id: str, permission_codes: list[str]) -> bool:
        """检查用户是否有所有权限"""
        permissions = await self.get_user_permissions(user_id)
        return all(code in permissions for code in permission_codes)

    async def has_role(self, user_id: str, role_code: str) -> bool:
        """检查用户是否有特定角色"""
        roles = await self.get_user_roles(user_id)
        return any(role.code == role_code for role in roles)

    async def add_role_to_user(self, user_id: str, role_id: int):
        """给用户添加角色"""
        stmt = user_roles.insert().values(user_id=user_id, role_id=role_id)
        await self.db.execute(stmt)
        await self.db.commit()

        # 清除缓存
        self.cache.delete(f"user:roles:{user_id}")
        self.cache.delete(f"user:permissions:{user_id}")

    async def remove_role_from_user(self, user_id: str, role_id: int):
        """移除用户的角色"""
        stmt = user_roles.delete().where(and_(user_roles.c.user_id == user_id, user_roles.c.role_id == role_id))
        await self.db.execute(stmt)
        await self.db.commit()

        # 清除缓存
        self.cache.delete(f"user:roles:{user_id}")
        self.cache.delete(f"user:permissions:{user_id}")

    async def get_role_by_code(self, role_code: str) -> Role | None:
        """根据代码获取角色"""
        stmt = select(Role).where(Role.code == role_code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_role(
        self,
        name: str,
        code: str,
        description: str | None = None,
        priority: int = 0,
        is_system: bool = False,
    ) -> Role:
        """创建角色"""
        role = Role(
            name=name,
            code=code,
            description=description,
            priority=priority,
            is_system=is_system,
            is_active=True,
        )
        self.db.add(role)
        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def create_permission(
        self,
        name: str,
        code: str,
        resource: str,
        action: str,
        description: str | None = None,
    ) -> Permission:
        """创建权限"""
        permission = Permission(
            name=name,
            code=code,
            resource=resource,
            action=action,
            description=description,
            is_active=True,
        )
        self.db.add(permission)
        await self.db.commit()
        await self.db.refresh(permission)
        return permission

    async def add_permission_to_role(self, role_id: int, permission_id: int):
        """给角色添加权限"""
        stmt = role_permissions.insert().values(role_id=role_id, permission_id=permission_id)
        await self.db.execute(stmt)
        await self.db.commit()

        # 清除相关用户的权限缓存
        # 这里需要查询所有拥有该角色的用户，然后清除他们的缓存
        # 为简化，可以选择清除所有用户权限缓存

    async def remove_permission_from_role(self, role_id: int, permission_id: int):
        """移除角色的权限"""
        stmt = role_permissions.delete().where(
            and_(
                role_permissions.c.role_id == role_id,
                role_permissions.c.permission_id == permission_id,
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()


async def init_default_roles_and_permissions(db: AsyncSession):
    """初始化默认角色和权限"""
    rbac_service = RBACService(db)

    # 检查是否已经初始化
    admin_role = await rbac_service.get_role_by_code("admin")
    if admin_role:
        return

        # 创建角色
    admin_role = await rbac_service.create_role(
        name="管理员",
        code="admin",
        description="系统管理员，拥有所有权限",
        priority=100,
        is_system=True,
    )

    user_role = await rbac_service.create_role(
        name="普通用户",
        code="user",
        description="普通用户，基本权限",
        priority=10,
        is_system=True,
    )

    trader_role = await rbac_service.create_role(
        name="交易员",
        code="trader",
        description="可以进行交易操作",
        priority=50,
        is_system=False,
    )

    # 创建权限
    permissions = [
        # 用户管理权限
        ("查看用户", "user.read", "user", "read", "查看用户信息"),
        ("创建用户", "user.create", "user", "create", "创建新用户"),
        ("更新用户", "user.update", "user", "update", "更新用户信息"),
        ("删除用户", "user.delete", "user", "delete", "删除用户"),
        # 策略管理权限
        ("查看策略", "strategy.read", "strategy", "read", "查看策略信息"),
        ("创建策略", "strategy.create", "strategy", "create", "创建新策略"),
        ("更新策略", "strategy.update", "strategy", "update", "更新策略"),
        ("删除策略", "strategy.delete", "strategy", "delete", "删除策略"),
        ("执行策略", "strategy.execute", "strategy", "execute", "执行策略"),
        # 投资组合权限
        ("查看组合", "portfolio.read", "portfolio", "read", "查看投资组合"),
        ("创建组合", "portfolio.create", "portfolio", "create", "创建投资组合"),
        ("更新组合", "portfolio.update", "portfolio", "update", "更新投资组合"),
        ("删除组合", "portfolio.delete", "portfolio", "delete", "删除投资组合"),
        # 交易权限
        ("查看订单", "order.read", "order", "read", "查看订单"),
        ("创建订单", "order.create", "order", "create", "创建订单"),
        ("取消订单", "order.cancel", "order", "cancel", "取消订单"),
        ("查看交易", "trade.read", "trade", "read", "查看交易记录"),
        # 行情权限
        ("查看行情", "market_data.read", "market_data", "read", "查看市场行情"),
        (
            "订阅行情",
            "market_data.subscribe",
            "market_data",
            "subscribe",
            "订阅实时行情",
        ),
        # 系统管理权限
        ("系统配置", "system.config", "system", "config", "系统配置管理"),
        ("系统监控", "system.monitor", "system", "monitor", "系统监控"),
        ("审计日志", "system.audit", "system", "audit", "查看审计日志"),
    ]

    created_permissions = {}
    for name, code, resource, action, desc in permissions:
        perm = await rbac_service.create_permission(name, code, resource, action, desc)
        created_permissions[code] = perm

        # 给管理员分配所有权限
    for perm in created_permissions.values():
        await rbac_service.add_permission_to_role(admin_role.id, perm.id)

        # 给普通用户分配基本权限
    basic_permissions = [
        "user.read",
        "strategy.read",
        "strategy.create",
        "strategy.update",
        "portfolio.read",
        "portfolio.create",
        "portfolio.update",
        "order.read",
        "trade.read",
        "market_data.read",
        "market_data.subscribe",
    ]
    for code in basic_permissions:
        perm = created_permissions.get(code)
        if perm:
            await rbac_service.add_permission_to_role(user_role.id, perm.id)

            # 给交易员分配交易权限
    trader_permissions = basic_permissions + [
        "order.create",
        "order.cancel",
        "strategy.execute",
    ]
    for code in trader_permissions:
        perm = created_permissions.get(code)
        if perm:
            await rbac_service.add_permission_to_role(trader_role.id, perm.id)

    print("✅ 默认角色和权限初始化完成")
