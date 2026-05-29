"""
企业级数据库连接池管理
支持主从读写分离、连接池、健康检查
"""

import logging
import os
import urllib.parse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from collections.abc import AsyncGenerator

try:
    # 确保优先加载项目根目录的 .env（仅当 python-dotenv 可用）
    # 在容器化环境中，我们禁用此处的 load_dotenv，以避免干扰由 Docker 注入的统一变量。
    pass
    # from dotenv import load_dotenv  # type: ignore
    # _ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
    # if _ROOT_ENV.exists():
    #     load_dotenv(str(_ROOT_ENV), override=False)
except Exception:
    # 忽略加载失败，继续使用系统环境变量
    pass

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """数据库配置"""

    def __init__(self):
        # 1. 优先从 DATABASE_URL 加载（全路径连接模式）
        self.database_url = os.getenv("DATABASE_URL", "").strip()

        # 2. 备选：从散装环境变量加载（独立服务模式）
        self.master_host = os.getenv("DB_MASTER_HOST", os.getenv("DB_HOST", "127.0.0.1"))
        self.master_port = int(os.getenv("DB_MASTER_PORT", os.getenv("DB_PORT", "5432")))
        self.database = os.getenv("DB_NAME", "quantmind")
        self.username = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "")

        # 初始化从库列表
        self.slave_hosts = os.getenv("DB_SLAVE_HOSTS", "")
        self.slave_list = [
            (host.split(":")[0], int(host.split(":")[1])) for host in self.slave_hosts.split(",") if host
        ]

        if self.database_url:
            logger.info(f"Using DATABASE_URL: {self.database_url.split('@')[-1]}")  # 隐藏密码
        else:
            logger.info(f"Database direct connect mode: {self.master_host}:{self.master_port}/{self.database}")

        # 连接池配置
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "20"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "30"))
        self.pool_timeout = float(os.getenv("DB_POOL_TIMEOUT", "30"))
        self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
        self.pool_pre_ping = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"

        # 连接配置
        self.echo = os.getenv("DB_ECHO", "false").lower() == "true"
        self.echo_pool = os.getenv("DB_ECHO_POOL", "false").lower() == "true"

    def get_master_url(self) -> str:
        """获取主库连接URL"""
        import socket

        # 强制 IP 物理转换逻辑：彻底终结 gaierror
        def resolve_to_ip(host_str):
            try:
                # 如果已经是 IP 则直接返回，否则强制解析
                return socket.gethostbyname(host_str.strip())
            except Exception:
                return host_str.strip()

        if self.database_url:
            url = self.database_url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url

        user = urllib.parse.quote(self.username)
        password = urllib.parse.quote(self.password)

        # 物理修正解析
        host = resolve_to_ip(self.master_host)

        return f"postgresql+asyncpg://{user}:{password}@" f"{host}:{self.master_port}/{self.database}"

    def get_slave_url(self, host: str, port: int) -> str:
        """获取从库连接URL"""
        user = urllib.parse.quote(self.username)
        password = urllib.parse.quote(self.password)
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{self.database}"


class DatabaseManager:
    """数据库连接池管理器"""

    def __init__(self, config: DatabaseConfig | None = None):
        self.config = config or DatabaseConfig()
        self._master_engine: AsyncEngine | None = None
        self._slave_engines: list[AsyncEngine] = []
        self._current_slave_index = 0
        self._master_session_factory: async_sessionmaker | None = None
        self._slave_session_factories: list[async_sessionmaker] = []
        self._initialized = False

    async def initialize(self):
        """初始化数据库连接池"""
        if self._initialized:
            logger.warning("DatabaseManager already initialized")
            return

        logger.info("Initializing database connection pools...")

        # 创建主库引擎
        master_url = self.config.get_master_url()
        logger.info(f"Creating master database engine with URL: {master_url}")
        self._master_engine = create_async_engine(
            master_url,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            pool_timeout=self.config.pool_timeout,
            pool_recycle=self.config.pool_recycle,
            pool_pre_ping=self.config.pool_pre_ping,
            echo=self.config.echo,
            echo_pool=self.config.echo_pool,
        )

        # 添加连接事件监听
        self._setup_engine_events(self._master_engine, "master")

        # 创建主库会话工厂
        self._master_session_factory = async_sessionmaker(
            self._master_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # 创建从库引擎
        for idx, (host, port) in enumerate(self.config.slave_list, 1):
            try:
                slave_engine = create_async_engine(
                    self.config.get_slave_url(host, port),
                    pool_size=self.config.pool_size // 2,  # 从库连接池减半
                    max_overflow=self.config.max_overflow // 2,
                    pool_timeout=self.config.pool_timeout,
                    pool_recycle=self.config.pool_recycle,
                    pool_pre_ping=self.config.pool_pre_ping,
                    echo=self.config.echo,
                    echo_pool=self.config.echo_pool,
                )

                self._setup_engine_events(slave_engine, f"slave-{idx}")
                self._slave_engines.append(slave_engine)

                # 创建从库会话工厂
                slave_session_factory = async_sessionmaker(
                    slave_engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                )
                self._slave_session_factories.append(slave_session_factory)

                logger.info(f"Slave database {idx} ({host}:{port}) initialized")
            except Exception as e:
                logger.error(f"Failed to initialize slave database {idx}: {e}")

        self._initialized = True
        logger.info("Database connection pools initialized: " f"1 master, {len(self._slave_engines)} slaves")

        # 执行健康检查
        await self.health_check()

    def _setup_engine_events(self, engine: AsyncEngine, name: str):
        """设置引擎事件监听"""

        @event.listens_for(engine.sync_engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            logger.debug(f"New connection to {name} database")

        @event.listens_for(engine.sync_engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            logger.debug(f"Connection checked out from {name} pool")

        @event.listens_for(engine.sync_engine, "checkin")
        def receive_checkin(dbapi_conn, connection_record):
            logger.debug(f"Connection returned to {name} pool")

    @asynccontextmanager
    async def get_master_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取主库会话 (用于写操作)"""
        if not self._initialized:
            await self.initialize()

        async with self._master_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Master session error: {e}")
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def get_slave_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取从库会话 (用于读操作，轮询负载均衡)"""
        if not self._initialized:
            await self.initialize()

        # 如果没有从库，降级到主库
        if not self._slave_session_factories:
            logger.warning("No slave databases available, using master for read")
            async with self.get_master_session() as session:
                yield session
                return

        # 轮询选择从库
        factory = self._slave_session_factories[self._current_slave_index]
        self._current_slave_index = (self._current_slave_index + 1) % len(self._slave_session_factories)

        async with factory() as session:
            try:
                yield session
            except Exception as e:
                logger.error(f"Slave session error: {e}")
                # 从库读取失败，降级到主库
                logger.warning("Slave read failed, fallback to master")
                async with self.get_master_session() as master_session:
                    yield master_session
            finally:
                await session.close()

    @asynccontextmanager
    async def get_session(self, read_only: bool = False) -> AsyncGenerator[AsyncSession, None]:
        """
        获取数据库会话 (自动读写分离)

        Args:
            read_only: 是否只读操作，True使用从库，False使用主库
        """
        if read_only:
            async with self.get_slave_session() as session:
                yield session
        else:
            async with self.get_master_session() as session:
                yield session

    async def health_check(self) -> dict:
        """健康检查"""
        result = {"master": False, "slaves": []}

        # 检查主库
        try:
            async with self._master_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                result["master"] = True
                logger.info("Master database health check: OK")
        except Exception as e:
            logger.error(f"Master database health check failed: {e}")
            result["master"] = False

        # 检查从库
        for idx, engine in enumerate(self._slave_engines, 1):
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                    result["slaves"].append({"index": idx, "healthy": True})
                    logger.info(f"Slave database {idx} health check: OK")
            except Exception as e:
                logger.error(f"Slave database {idx} health check failed: {e}")
                result["slaves"].append({"index": idx, "healthy": False})

        return result

    async def get_pool_status(self) -> dict:
        """获取连接池状态"""
        status = {}

        # 主库连接池状态
        if self._master_engine:
            pool = self._master_engine.pool
            status["master"] = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "total": pool.size() + pool.overflow(),
            }

        # 从库连接池状态
        status["slaves"] = []
        for idx, engine in enumerate(self._slave_engines, 1):
            pool = engine.pool
            status["slaves"].append(
                {
                    "index": idx,
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "total": pool.size() + pool.overflow(),
                }
            )

        return status

    async def close(self):
        """关闭所有数据库连接"""
        logger.info("Closing database connections...")

        if self._master_engine:
            await self._master_engine.dispose()
            logger.info("Master database connections closed")

        for idx, engine in enumerate(self._slave_engines, 1):
            await engine.dispose()
            logger.info(f"Slave database {idx} connections closed")

        self._initialized = False
        logger.info("All database connections closed")


# 全局数据库管理器实例
_db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """获取全局数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


@asynccontextmanager
async def get_session(read_only: bool = False) -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的便捷函数

    Usage:
        async with get_session() as session:
            # 写操作
            pass

        async with get_session(read_only=True) as session:
            # 读操作
            pass
    """
    db_manager = get_db_manager()
    async with db_manager.get_session(read_only=read_only) as session:
        yield session


async def init_database():
    """初始化数据库连接池"""
    db_manager = get_db_manager()
    await db_manager.initialize()


async def close_database():
    """关闭数据库连接池"""
    db_manager = get_db_manager()
    await db_manager.close()
