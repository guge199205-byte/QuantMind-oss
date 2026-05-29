import secrets
import string
from datetime import datetime
from typing import List, Optional, Tuple

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.user_app.models.api_key import ApiKey
from backend.services.api.user_app.schemas.api_key import (
    ApiKeyBootstrapResponse,
    ApiKeyCreate,
    ApiKeyInfo,
    ApiKeyResponse,
    ApiKeyRotateSecretResponse,
    ApiKeyUpdate,
)

# Reuse the same pwd_context if possible, or create a specific one
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class ApiKeyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_keys(self, env: str = "live") -> tuple[str, str]:
        """Generate Access Key and Secret Key"""
        # Access Key: qm_{env}_{16_random_alnum}
        random_part = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
        access_key = f"qm_{env}_{random_part}"

        # Secret Key: sk_{32_random_alnum}
        secret_part = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        secret_key = f"sk_{secret_part}"

        return access_key, secret_key

    def _hash_secret(self, secret: str) -> str:
        return pwd_context.hash(secret)

    def verify_secret(self, secret: str, hashed_secret: str) -> bool:
        return pwd_context.verify(secret, hashed_secret)

    async def create_api_key(self, user_id: str, tenant_id: str, data: ApiKeyCreate) -> ApiKeyResponse:
        access_key, secret_key = self._generate_keys()
        secret_hash = self._hash_secret(secret_key)

        db_key = ApiKey(
            user_id=user_id,
            tenant_id=tenant_id,
            access_key=access_key,
            secret_hash=secret_hash,
            name=data.name,
            permissions=data.permissions,
            expires_at=data.expires_at,
            is_active=True,
        )
        self.db.add(db_key)
        await self.db.commit()
        await self.db.refresh(db_key)

        # Return response with the raw secret key (only time it's visible)
        return ApiKeyResponse(
            id=db_key.id,
            access_key=db_key.access_key,
            secret_key=secret_key,  # The raw secret
            name=db_key.name,
            permissions=db_key.permissions,
            is_active=db_key.is_active,
            created_at=db_key.created_at,
            expires_at=db_key.expires_at,
        )

    async def get_user_keys(self, user_id: str, tenant_id: str) -> list[ApiKeyInfo]:
        stmt = (
            select(ApiKey)
            .where(
                ApiKey.user_id == user_id,
                ApiKey.tenant_id == tenant_id,
                # We might want to include deleted checks if soft delete is added later
            )
            .order_by(ApiKey.created_at.desc())
        )

        result = await self.db.execute(stmt)
        keys = result.scalars().all()
        return [ApiKeyInfo.from_orm(k) for k in keys]

    async def update_api_key(self, user_id: str, access_key: str, data: ApiKeyUpdate) -> ApiKeyInfo | None:
        # First ensure it belongs to user
        stmt = select(ApiKey).where(ApiKey.access_key == access_key, ApiKey.user_id == user_id)
        result = await self.db.execute(stmt)
        key = result.scalar_one_or_none()

        if not key:
            return None

        if data.name is not None:
            key.name = data.name
        if data.permissions is not None:
            key.permissions = data.permissions
        if data.is_active is not None:
            key.is_active = data.is_active

        await self.db.commit()
        await self.db.refresh(key)
        return ApiKeyInfo.from_orm(key)

    async def delete_api_key(self, user_id: str, access_key: str) -> bool:
        stmt = select(ApiKey).where(ApiKey.access_key == access_key, ApiKey.user_id == user_id)
        result = await self.db.execute(stmt)
        key = result.scalar_one_or_none()

        if not key:
            return False

        await self.db.delete(key)
        await self.db.commit()
        return True

    async def validate_key(self, access_key: str) -> ApiKey | None:
        """Internal use: Validate key and update last_used_at"""
        stmt = select(ApiKey).where(ApiKey.access_key == access_key)
        result = await self.db.execute(stmt)
        key = result.scalar_one_or_none()

        if not key or not key.is_active:
            return None

        if key.expires_at and key.expires_at < datetime.now():
            return None

        # Update last_used (async, maybe optimize to not update on every hit)
        key.last_used_at = datetime.now()
        await self.db.commit()

        return key

    async def bootstrap_default_key(self, user_id: str, tenant_id: str) -> ApiKeyBootstrapResponse:
        existing = await self.get_user_keys(user_id=user_id, tenant_id=tenant_id)
        if existing:
            latest = existing[0]
            return ApiKeyBootstrapResponse(
                **latest.model_dump(),
                secret_key=None,
                just_created=False,
            )

        created = await self.create_api_key(
            user_id=user_id,
            tenant_id=tenant_id,
            data=ApiKeyCreate(
                name="交易系统默认Key",
                permissions=["trade.read", "trade.write"],
            ),
        )
        return ApiKeyBootstrapResponse(
            id=created.id,
            access_key=created.access_key,
            name=created.name,
            permissions=created.permissions,
            is_active=created.is_active,
            created_at=created.created_at,
            expires_at=created.expires_at,
            last_used_at=None,
            secret_key=created.secret_key,
            just_created=True,
        )

    async def rotate_secret(
        self, user_id: str, tenant_id: str, access_key: str
    ) -> ApiKeyRotateSecretResponse | None:
        stmt = select(ApiKey).where(
            ApiKey.access_key == access_key,
            ApiKey.user_id == user_id,
            ApiKey.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        key = result.scalar_one_or_none()
        if key is None:
            return None

        _, secret_key = self._generate_keys()
        key.secret_hash = self._hash_secret(secret_key)
        key.is_active = True
        await self.db.commit()
        return ApiKeyRotateSecretResponse(
            access_key=access_key,
            secret_key=secret_key,
        )
