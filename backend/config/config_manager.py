"""
配置管理器

负责加载和管理所有配置，支持环境变量和配置文件。
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DataSourceType(Enum):
    """数据源类型"""

    TENCENT = "tencent"
    BAOSTOCK = "baostock"
    TUSHARE = "tushare"


@dataclass
class DataSourceConfig:
    """数据源配置"""

    name: str
    enabled: bool
    priority: int
    api_url: str | None = None
    api_token: str | None = None
    api_key: str | None = None
    timeout: int = 10
    retry_times: int = 3
    capabilities: list[str] = field(default_factory=list)

    def __post_init__(self):
        """配置验证"""
        if self.priority < 1:
            raise ValueError(f"Priority must be >= 1, got {self.priority}")

        if self.timeout < 1:
            raise ValueError(f"Timeout must be >= 1, got {self.timeout}")


@dataclass
class CacheConfig:
    """缓存配置"""

    enabled: bool = True
    ttl: int = 10  # 默认10秒
    max_size: int = 1000

    def __post_init__(self):
        """配置验证"""
        if self.ttl < 0:
            raise ValueError(f"TTL must be >= 0, got {self.ttl}")

        if self.max_size < 1:
            raise ValueError(f"Max size must be >= 1, got {self.max_size}")


class ConfigManager:
    """配置管理器

    负责加载和管理所有配置，支持环境变量和配置文件。
    """

    def __init__(self, config_file: str | None = None):
        """初始化配置管理器

        Args:
            config_file: 配置文件路径（可选）
        """
        self._config_file = config_file
        self._data_source_configs: dict[str, DataSourceConfig] = {}
        self._cache_config: CacheConfig = CacheConfig()
        self._load_config()

    def _load_config(self) -> None:
        """加载配置"""
        # 优先从环境变量加载
        self._load_from_env()

        # 如果指定了配置文件，从文件加载（覆盖环境变量）
        if self._config_file:
            self._load_from_file()

        logger.info(f"Loaded {len(self._data_source_configs)} data source configs")

    def _load_from_env(self) -> None:
        """从环境变量加载配置"""
        # 腾讯财经配置
        self._data_source_configs[DataSourceType.TENCENT.value] = DataSourceConfig(
            name=DataSourceType.TENCENT.value,
            enabled=self._get_bool_env("TENCENT_ENABLED", True),
            priority=self._get_int_env("TENCENT_PRIORITY", 1),
            timeout=self._get_int_env("TENCENT_TIMEOUT", 10),
            capabilities=["market_overview", "stock_quotes", "indices"],
        )

        # Baostock 配置（主要用于股票列表/搜索）
        self._data_source_configs[DataSourceType.BAOSTOCK.value] = DataSourceConfig(
            name=DataSourceType.BAOSTOCK.value,
            enabled=self._get_bool_env("BAOSTOCK_ENABLED", True),
            priority=self._get_int_env("BAOSTOCK_PRIORITY", 2),
            timeout=self._get_int_env("BAOSTOCK_TIMEOUT", 10),
            capabilities=["stock_list", "search_stocks"],
        )

        # Tushare 配置
        tushare_token = os.getenv("TUSHARE_TOKEN")
        if not tushare_token:
            logger.warning("TUSHARE_TOKEN not set in environment")

        self._data_source_configs[DataSourceType.TUSHARE.value] = DataSourceConfig(
            name=DataSourceType.TUSHARE.value,
            enabled=self._get_bool_env("TUSHARE_ENABLED", True),
            priority=self._get_int_env("TUSHARE_PRIORITY", 1),
            api_token=tushare_token,
            timeout=self._get_int_env("TUSHARE_TIMEOUT", 10),
            capabilities=["fundamental_data", "search_stocks", "historical_data"],
        )

        # 缓存配置
        self._cache_config = CacheConfig(
            enabled=self._get_bool_env("CACHE_ENABLED", True),
            ttl=self._get_int_env("CACHE_TTL", 10),
            max_size=self._get_int_env("CACHE_MAX_SIZE", 1000),
        )

    def _load_from_file(self) -> None:
        """从配置文件加载配置"""
        # TODO: 实现从 YAML 或 JSON 文件加载配置

    def get_data_source_config(self, source_type: str) -> DataSourceConfig | None:
        """获取数据源配置

        Args:
            source_type: 数据源类型

        Returns:
            数据源配置，如果不存在返回 None
        """
        return self._data_source_configs.get(source_type)

    def get_all_data_source_configs(self) -> list[DataSourceConfig]:
        """获取所有数据源配置，按优先级排序

        Returns:
            数据源配置列表
        """
        configs = list(self._data_source_configs.values())
        # 按优先级排序（数字越小优先级越高）
        configs.sort(key=lambda x: x.priority)
        return configs

    def get_enabled_data_source_configs(self) -> list[DataSourceConfig]:
        """获取所有已启用的数据源配置，按优先级排序

        Returns:
            已启用的数据源配置列表
        """
        return [c for c in self.get_all_data_source_configs() if c.enabled]

    def get_cache_config(self) -> CacheConfig:
        """获取缓存配置

        Returns:
            缓存配置
        """
        return self._cache_config

    @staticmethod
    def _get_bool_env(key: str, default: bool) -> bool:
        """获取布尔类型环境变量"""
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    @staticmethod
    def _get_int_env(key: str, default: int) -> int:
        """获取整数类型环境变量"""
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            logger.warning(f"Invalid int value for {key}: {value}, using default {default}")
            return default
