"""Database connection and session management."""

import logging
from typing import Optional
from collections.abc import AsyncGenerator

from redis.asyncio import Redis
from redis.sentinel import Sentinel
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .market_config import settings

logger = logging.getLogger(__name__)

_ASYNC_DRIVER_MAP = {
    "postgresql": "postgresql+asyncpg",
    "postgres": "postgresql+asyncpg",
    "postgresql+psycopg2": "postgresql+asyncpg",
    "postgresql+psycopg": "postgresql+asyncpg",
    "postgresql+asyncpg": "postgresql+asyncpg",
}


def _build_async_database_url(raw_url: str) -> str:
    url = make_url(raw_url)
    drivername = _ASYNC_DRIVER_MAP.get(url.drivername, url.drivername)
    if drivername == "postgresql" or drivername == "postgres":
        drivername = "postgresql+asyncpg"
    # `str(URL)` 会隐藏密码为 `***`，这里必须保留真实凭据用于实际建连。
    return url.set(drivername=drivername).render_as_string(hide_password=False)


def _create_engine():
    return create_async_engine(
        _build_async_database_url(settings.DATABASE_URL),
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        echo=settings.DB_ECHO,
        future=True,
    )


engine = _create_engine()
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Redis Sentinel
redis_sentinel = Sentinel(
    settings.REDIS_SENTINELS,
    socket_timeout=0.5,
    password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_redis() -> Redis:
    """Get Redis connection"""
    try:
        if settings.REDIS_USE_SENTINEL:
            master = redis_sentinel.master_for(
                settings.REDIS_MASTER_NAME,
                socket_timeout=0.5,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                db=settings.REDIS_DB,
            )
            return Redis(connection_pool=master.connection_pool)
        else:
            return Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                db=settings.REDIS_DB,
            )
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}, returning None")
        return None


async def init_db():
    """Initialize database connectivity only.

    Schema creation is handled by explicit migrations/bootstrap, not service startup.
    """

    try:
        global engine, AsyncSessionLocal  # noqa: F824
        expected_url = _build_async_database_url(settings.DATABASE_URL)
        if str(engine.url) != expected_url:
            await engine.dispose()
            engine = _create_engine()
            AsyncSessionLocal.configure(bind=engine)
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connectivity verified")
    except Exception:
        logger.exception("Database initialization failed")
        raise


async def close_db():
    """Close database connection"""
    await engine.dispose()
    logger.info("Database connection closed")
