"""
统一数据库连接池管理 (同步路径)
提供基于 psycopg2 的同步 SQLAlchemy 连接池，用于策略存储、AI 向导等同步 I/O 场景。
"""

import logging
import os
from contextlib import contextmanager
from typing import Dict, Optional
from collections.abc import Generator
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)


class PoolConfig:
    def __init__(self, pool_size: int = 10, max_overflow: int = 20, pool_pre_ping: bool = True):
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_pre_ping = pool_pre_ping


class DatabasePool:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._engines = {}
            cls._instance._session_factories = {}
        return cls._instance

    def register_database(self, name: str, url: str, config: PoolConfig | None = None):
        """注册一个数据库连接池"""
        if name in self._engines:
            return

        if config is None:
            config = PoolConfig()

        # 确保是同步驱动
        if "asyncpg" in url:
            url = url.replace("asyncpg", "psycopg2")
        elif url.startswith("postgresql://") and "psycopg2" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgres://") and "psycopg2" not in url:
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)

        try:
            engine = create_engine(
                url,
                pool_size=config.pool_size,
                max_overflow=config.max_overflow,
                pool_pre_ping=config.pool_pre_ping,
                pool_recycle=3600,
            )
            self._engines[name] = engine
            self._session_factories[name] = sessionmaker(bind=engine, autocommit=False, autoflush=False)
            logger.info(f"Database pool '{name}' registered successfully.")
        except Exception as e:
            logger.error(f"Failed to register database pool '{name}': {e}")
            raise

    def get_session(self, name: str = "postgres") -> Session:
        """获取指定数据库的 Session"""
        if name not in self._session_factories:
            # 尝试自动从环境变量注册默认库
            if name == "postgres":
                init_default_databases()

            if name not in self._session_factories:
                raise RuntimeError(f"Database pool '{name}' is not registered.")

        return self._session_factories[name]()


_pool = DatabasePool()


def get_database_pool() -> DatabasePool:
    return _pool


@contextmanager
def get_db(name: str = "postgres") -> Generator[Session, None, None]:
    """同步 DB Session 注入器/上下文管理器"""
    session = _pool.get_session(name)
    try:
        yield session
    finally:
        session.close()


def init_default_databases(pool_size: int = 20, max_overflow: int = 10):
    """初始化默认数据库连接 (从环境变量读取)"""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        # 拼接模式
        host = os.getenv("DB_MASTER_HOST", "localhost")
        port = os.getenv("DB_MASTER_PORT", "5432")
        user = os.getenv("DB_USER", "quantmind")
        password = quote_plus(os.getenv("DB_PASSWORD", ""))
        db_name = os.getenv("DB_NAME", "quantmind")
        url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"

    _pool.register_database("postgres", url, PoolConfig(pool_size=pool_size, max_overflow=max_overflow))
