"""
Seed Data Service
初始化默认数据
"""

import asyncio
import logging

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.user_app.models.user import User, UserProfile
from backend.services.api.user_app.services.rbac_service import (
    RBACService,
    init_default_roles_and_permissions,
)

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def init_admin_data(db: AsyncSession):
    """初始化管理员数据"""
    logger.info("Starting admin data initialization...")
    default_tenant_id = "default"

    # 1. 确保RBAC角色存在
    await init_default_roles_and_permissions(db)

    # 2. 检查管理员用户是否存在
    stmt = select(User).where(
        User.username == "admin",
        User.tenant_id == default_tenant_id,
    )
    result = await db.execute(stmt)
    admin_user = result.scalar_one_or_none()

    import bcrypt

    if not admin_user:
        logger.info("Creating default admin user...")
        # Use bcrypt directly to avoid passlib compatibility issues with newer bcrypt versions
        # admin123 hash
        hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8")

        admin_user = User(
            user_id="00000001",
            tenant_id=default_tenant_id,
            username="admin",
            email="admin@quantmind.com",
            password_hash=hashed,
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        db.add(admin_user)
        await db.commit()
        await db.refresh(admin_user)

        # 分配管理员角色
        rbac_service = RBACService(db)
        admin_role = await rbac_service.get_role_by_code("admin")
        if admin_role:
            # Check if already has role (unlikely for new user but good practice)
            roles = await rbac_service.get_user_roles(admin_user.user_id)
            if not any(r.code == "admin" for r in roles):
                await rbac_service.add_role_to_user(admin_user.user_id, admin_role.id)

    # 3. 检查/更新管理员档案
    stmt = select(UserProfile).where(
        UserProfile.user_id == admin_user.user_id,
        UserProfile.tenant_id == default_tenant_id,
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    default_preferences = {
        "theme": "dark",
        "language": "zh-CN",
        "dashboard_layout": "default",
    }

    default_notifications = {"email": True, "push": True, "marketing": False}

    if not profile:
        logger.info("Creating admin profile...")
        profile = UserProfile(
            user_id=admin_user.user_id,
            tenant_id=default_tenant_id,
            display_name="System Administrator",
            bio="QuantMind 系统管理员",
            location="Server Room",
            avatar_url="https://ui-avatars.com/api/?name=Admin&background=0D8ABC&color=fff",
            trading_experience="advanced",
            risk_tolerance="high",
            preferences=default_preferences,
            notification_settings=default_notifications,
        )
        db.add(profile)
    else:
        # Update if fields are missing
        if not profile.preferences:
            profile.preferences = default_preferences
        if not profile.notification_settings:
            profile.notification_settings = default_notifications

    await db.commit()
    logger.info("Admin data initialization completed.")


if __name__ == "__main__":
    # Allow running directly
    import os

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    async def main():
        # Use DATABASE_URL from environment variable
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is not set")

        engine = create_async_engine(db_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            await init_admin_data(session)
        await engine.dispose()

    asyncio.run(main())
