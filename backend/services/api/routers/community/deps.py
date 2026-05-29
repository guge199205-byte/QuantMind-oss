from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.database_manager_v2 import get_session


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with get_session(read_only=False) as session:
        yield session


async def get_readonly_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for read-only database sessions."""
    async with get_session(read_only=True) as session:
        yield session
