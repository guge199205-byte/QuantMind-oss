"""
Database session helpers for User Service.

提供 FastAPI 依赖注入用的异步会话生成器，基于 shared/database_manager_v2。
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from backend.shared.database_manager_v2 import get_session


@asynccontextmanager
async def _session_scope(read_only: bool = False):
    async with get_session(read_only=read_only) as session:
        yield session


async def get_db() -> AsyncGenerator:
    """获取可写会话（默认）。"""
    async with _session_scope(read_only=False) as session:
        yield session


async def get_readonly_db() -> AsyncGenerator:
    """获取只读会话。"""
    async with _session_scope(read_only=True) as session:
        yield session
