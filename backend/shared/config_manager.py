import logging
import os
from pathlib import Path
from typing import Any, Dict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

try:
    from dotenv import load_dotenv

    _ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
    if _ROOT_ENV.exists():
        # 不覆盖运行时环境变量，确保 Docker/K8s 注入值优先
        load_dotenv(str(_ROOT_ENV), override=False)
except Exception:
    pass

logger = logging.getLogger(__name__)


class UnifiedConfigManager:
    """
    统一配置管理器
    优先级：数据库配置 > 环境变量 > .env文件
    """

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.db_url = os.getenv("DATABASE_URL")
        # 默认关闭：避免数据库中的 system_settings 覆盖 .env / 运行时环境变量。
        # 如需恢复旧行为，显式设置 UNIFIED_CONFIG_DB_OVERRIDE_ENABLED=true。
        self.db_override_enabled = os.getenv("UNIFIED_CONFIG_DB_OVERRIDE_ENABLED", "false").lower() == "true"
        self._config: dict[str, Any] = {}

    async def load_all(self):
        """从数据库加载并覆盖环境变量"""
        if not self.db_override_enabled:
            logger.info("Unified DB config override is disabled " "(UNIFIED_CONFIG_DB_OVERRIDE_ENABLED=false)")
            return

        if not self.db_url:
            logger.warning("DATABASE_URL not set, skipping DB config load")
            return

        try:
            # 兼容 asyncpg 驱动前缀
            engine_url = self.db_url
            if "postgresql://" in engine_url:
                engine_url = engine_url.replace("postgresql://", "postgresql+psycopg2://")

            engine = create_async_engine(engine_url)

            async with engine.connect() as conn:
                # 获取 global 配置和当前服务特有配置
                query = text("""
                    SELECT config_key, config_value FROM system_settings 
                    WHERE service_name = 'global' OR service_name = :service
                """)
                result = await conn.execute(query, {"service": self.service_name})

                for row in result:
                    key, value = row[0], row[1]
                    # 动态注入到当前进程的环境变量
                    os.environ[key] = str(value)
                    self._config[key] = value

            await engine.dispose()
            logger.info(f"✅ Successfully loaded {len(self._config)} configs from DB for {self.service_name}")

        except Exception as e:
            logger.error(f"❌ Failed to load config from DB: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return os.getenv(key, default)


config_manager = None


async def init_unified_config(service_name: str):
    global config_manager
    config_manager = UnifiedConfigManager(service_name)
    await config_manager.load_all()
    return config_manager


def get_config() -> UnifiedConfigManager:
    """获取全局配置管理器"""
    if config_manager is None:
        raise RuntimeError("Config manager not initialized. Call init_unified_config first.")
    return config_manager
