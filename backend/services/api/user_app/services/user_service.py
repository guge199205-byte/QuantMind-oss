"""
User Service - 用户业务逻辑
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import or_, select, update

from backend.services.api.user_app.config import settings
from backend.services.api.user_app.models.user import User, UserProfile
from backend.services.api.user_app.schemas.user import (
    UserDetailResponse,
    UserProfileResponse,
    UserResponse,
)
from backend.shared.database_manager_v2 import get_session
from backend.shared.redis_sentinel_client import get_redis_sentinel_client

logger = logging.getLogger(__name__)


class UserService:
    """用户服务"""

    def __init__(self):
        self.redis_client = get_redis_sentinel_client()

    async def get_user_by_id(self, user_id: str, tenant_id: str, use_cache: bool = True) -> User | None:
        """根据ID获取用户"""
        # 尝试从缓存获取
        if use_cache:
            cache_key = f"user:{tenant_id}:{user_id}"
            cached = self.redis_client.get(cache_key, use_slave=True)
            if cached:
                logger.info(f"User cache hit: {user_id}")
                # 这里简化处理，实际应反序列化为User对象

        # 从数据库查询（使用从库）
        async with get_session(read_only=True) as session:
            result = await session.execute(
                select(User).where(
                    User.user_id == user_id,
                    User.tenant_id == tenant_id,
                    User.is_deleted == False,
                )
            )
            user = result.scalar_one_or_none()

            if user and use_cache:
                # 缓存用户信息
                cache_key = f"user:{tenant_id}:{user_id}"
                # 简化：实际应序列化整个对象
                self.redis_client.setex(cache_key, settings.CACHE_TTL_USER_PROFILE, user.username.encode())

            return user

    async def get_user_by_username(self, username: str, tenant_id: str) -> User | None:
        """根据用户名获取用户"""
        async with get_session(read_only=True) as session:
            result = await session.execute(
                select(User).where(
                    User.username == username,
                    User.tenant_id == tenant_id,
                    User.is_deleted == False,
                )
            )
            return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str, tenant_id: str) -> User | None:
        """根据邮箱获取用户"""
        async with get_session(read_only=True) as session:
            result = await session.execute(
                select(User).where(
                    User.email == email,
                    User.tenant_id == tenant_id,
                    User.is_deleted == False,
                )
            )
            return result.scalar_one_or_none()

    async def get_user_by_phone(self, phone: str, tenant_id: str) -> User | None:
        """根据手机号获取用户"""
        async with get_session(read_only=True) as session:
            result = await session.execute(
                select(User).where(
                    User.phone_number == phone,
                    User.tenant_id == tenant_id,
                    User.is_deleted == False,
                )
            )
            return result.scalar_one_or_none()

    async def search_users(
        self,
        tenant_id: str,
        query: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        """搜索用户"""
        async with get_session(read_only=True) as session:
            # 构建查询
            stmt = select(User).where(
                User.is_deleted == False,
                User.tenant_id == tenant_id,
            )

            if query:
                stmt = stmt.where(
                    or_(
                        User.username.ilike(f"%{query}%"),
                        User.email.ilike(f"%{query}%"),
                    )
                )

            if is_active is not None:
                stmt = stmt.where(User.is_active == is_active)

            # 计算总数
            from sqlalchemy import func

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = await session.scalar(count_stmt)

            # 分页
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
            result = await session.execute(stmt)
            users = result.scalars().all()

            return list(users), total or 0

    async def update_user(self, user_id: str, tenant_id: str, **updates) -> User | None:
        """更新用户信息"""
        async with get_session(read_only=False) as session:
            result = await session.execute(
                select(User).where(
                    User.user_id == user_id,
                    User.tenant_id == tenant_id,
                    User.is_deleted == False,
                )
            )
            user = result.scalar_one_or_none()

            if not user:
                return None

            # 更新字段
            for key, value in updates.items():
                if hasattr(user, key) and value is not None:
                    setattr(user, key, value)

            user.updated_at = datetime.now()
            await session.commit()
            await session.refresh(user)

            # 清除缓存
            cache_key = f"user:{tenant_id}:{user_id}"
            self.redis_client.delete(cache_key)

            logger.info(f"User updated: {user_id}")
            return user

    async def deactivate_user(self, user_id: str, tenant_id: str) -> bool:
        """停用用户"""
        async with get_session(read_only=False) as session:
            result = await session.execute(
                update(User)
                .where(User.user_id == user_id, User.tenant_id == tenant_id)
                .values(is_active=False, updated_at=datetime.now())
            )
            await session.commit()

            # 清除缓存
            cache_key = f"user:{tenant_id}:{user_id}"
            self.redis_client.delete(cache_key)

            return result.rowcount > 0

    async def soft_delete_user(self, user_id: str, tenant_id: str) -> bool:
        """软删除用户"""
        async with get_session(read_only=False) as session:
            result = await session.execute(
                update(User)
                .where(User.user_id == user_id, User.tenant_id == tenant_id)
                .values(
                    is_deleted=True,
                    deleted_at=datetime.now(),
                    updated_at=datetime.now(),
                )
            )
            await session.commit()

            # 清除缓存
            cache_key = f"user:{tenant_id}:{user_id}"
            self.redis_client.delete(cache_key)

            logger.info(f"User soft deleted: {user_id}")
            return result.rowcount > 0

    async def get_user_detail(self, user_id: str, tenant_id: str) -> UserDetailResponse | None:
        """获取用户详细信息（包含档案）"""
        async with get_session(read_only=True) as session:
            # 获取用户
            user_result = await session.execute(
                select(User).where(
                    User.user_id == user_id,
                    User.tenant_id == tenant_id,
                    User.is_deleted == False,
                )
            )
            user = user_result.scalar_one_or_none()

            if not user:
                return None

            # 获取档案
            profile_result = await session.execute(
                select(UserProfile).where(
                    UserProfile.user_id == user_id,
                    UserProfile.tenant_id == tenant_id,
                )
            )
            profile = profile_result.scalar_one_or_none()

            if not profile:
                return None

            return UserDetailResponse(
                user=UserResponse.from_orm(user),
                profile=UserProfileResponse.from_orm(profile),
            )
