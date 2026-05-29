#!/usr/bin/env python3
"""
股票查询功能配置文件
包含数据源配置、缓存配置等
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class Environment(Enum):
    """环境类型"""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


@dataclass
class DataSourceConfig:
    """数据源配置"""

    # Tushare配置
    tushare_token: str = os.getenv("TUSHARE_TOKEN", "")
    use_tushare: bool = bool(tushare_token)

    # 本地数据库配置
    use_local_db: bool = True
    db_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:@localhost:5432/quantmind")

    # 请求配置
    request_timeout: int = 30  # 请求超时时间（秒）
    max_retries: int = 3  # 最大重试次数
    retry_delay: float = 1.0  # 重试延迟（秒）

    # 并发配置
    max_concurrent_requests: int = 10  # 最大并发请求数
    rate_limit_per_second: int = 50  # 每秒最大请求数


@dataclass
class CacheConfig:
    """缓存配置"""

    # 内存缓存配置
    use_memory_cache: bool = True
    memory_cache_size: int = 1000  # 内存缓存最大条目数
    memory_cache_ttl: int = 300  # 内存缓存TTL（秒）

    # Redis缓存配置
    use_redis_cache: bool = False
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_password: str | None = os.getenv("REDIS_PASSWORD", "")
    redis_ttl: int = 3600  # Redis缓存TTL（秒）

    # 缓存键前缀
    cache_key_prefix: str = "stock_query"

    # 不同数据类型的缓存TTL
    cache_ttl_config: dict[str, int] = None

    def __post_init__(self):
        if self.cache_ttl_config is None:
            self.cache_ttl_config = {
                "stock_info": 3600,  # 股票基础信息：1小时
                "realtime_quote": 60,  # 实时行情：1分钟
                "historical_data": 1800,  # 历史数据：30分钟
                "technical_indicator": 900,  # 技术指标：15分钟
                "search_result": 600,  # 搜索结果：10分钟
                "hot_stocks": 300,  # 热门股票：5分钟
            }


@dataclass
class DataConfig:
    """数据配置"""

    # 默认查询参数
    default_limit: int = 20  # 默认查询数量限制
    max_limit: int = 1000  # 最大查询数量限制

    # 历史数据配置
    max_historical_days: int = 365  # 最大历史数据天数
    default_historical_days: int = 30  # 默认历史数据天数

    # 技术指标配置
    default_indicators: list[str] = None
    available_indicators: dict[str, str] = None

    # 市场配置
    supported_markets: list[str] = None
    market_trading_hours: dict[str, dict[str, str]] = None

    def __post_init__(self):
        if self.default_indicators is None:
            self.default_indicators = [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
            ]

        if self.available_indicators is None:
            self.available_indicators = {
                # 基础指标
                "open": "开盘价",
                "high": "最高价",
                "low": "最低价",
                "close": "收盘价",
                "volume": "成交量",
                "amount": "成交额",
                "chg": "涨跌额",
                "chg_pct": "涨跌幅",
                # 技术指标
                "ma5": "5日均线",
                "ma10": "10日均线",
                "ma20": "20日均线",
                "ma60": "60日均线",
                "rsi": "RSI指标",
                "macd": "MACD指标",
                "kdj_k": "KDJ-K值",
                "kdj_d": "KDJ-D值",
                "kdj_j": "KDJ-J值",
                "boll_upper": "布林上轨",
                "boll_mid": "布林中轨",
                "boll_lower": "布林下轨",
            }

        if self.supported_markets is None:
            self.supported_markets = ["SH", "SZ", "BJ"]  # 上海、深圳、北京

        if self.market_trading_hours is None:
            self.market_trading_hours = {
                "SH": {
                    "morning_start": "09:30",
                    "morning_end": "11:30",
                    "afternoon_start": "13:00",
                    "afternoon_end": "15:00",
                },
                "SZ": {
                    "morning_start": "09:30",
                    "morning_end": "11:30",
                    "afternoon_start": "13:00",
                    "afternoon_end": "15:00",
                },
                "BJ": {
                    "morning_start": "09:30",
                    "morning_end": "11:30",
                    "afternoon_start": "13:00",
                    "afternoon_end": "15:00",
                },
            }


@dataclass
class LoggingConfig:
    """日志配置"""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str | None = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5

    # 不同模块的日志级别
    module_levels: dict[str, str] = None

    def __post_init__(self):
        if self.module_levels is None:
            self.module_levels = {
                "stock_query.services": "INFO",
                "stock_query.controllers": "INFO",
                "shared.cache": "WARNING",
            }


@dataclass
class WebConfig:
    """Web服务配置"""

    host: str = "127.0.0.1"  # 默认localhost，Docker设置为0.0.0.0
    port: int = 5000
    debug: bool = False
    threaded: bool = True

    # CORS配置
    cors_origins: list[str] = None
    cors_methods: list[str] = None
    cors_headers: list[str] = None

    # 安全配置
    secret_key: str = "your-secret-key-change-in-production"

    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = ["*"]

        if self.cors_methods is None:
            self.cors_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]

        if self.cors_headers is None:
            self.cors_headers = ["Content-Type", "Authorization"]


class StockQueryConfig:
    """股票查询功能主配置类"""

    def __init__(self, environment: Environment = Environment.DEVELOPMENT):
        self.environment = environment

        # 初始化各模块配置
        self.datasource = DataSourceConfig()
        self.cache = CacheConfig()
        self.data = DataConfig()
        self.logging = LoggingConfig()
        self.web = WebConfig()

        # 根据环境调整配置
        self._adjust_config_by_environment()

        # 从环境变量加载配置
        self._load_from_environment()

    def _adjust_config_by_environment(self):
        """根据环境调整配置"""
        if self.environment == Environment.DEVELOPMENT:
            self.web.debug = True
            self.logging.level = "DEBUG"
            self.cache.use_redis_cache = False

        elif self.environment == Environment.TESTING:
            self.web.debug = False
            self.logging.level = "INFO"
            self.cache.use_redis_cache = False
            self.datasource.request_timeout = 10

        elif self.environment == Environment.PRODUCTION:
            self.web.debug = False
            self.logging.level = "WARNING"
            self.cache.use_redis_cache = True
            self.datasource.max_concurrent_requests = 20
            self.web.secret_key = os.environ.get("SECRET_KEY", self.web.secret_key)

    def _load_from_environment(self):
        """从环境变量加载配置"""
        # 数据源配置
        self.datasource.tushare_token = os.environ.get("TUSHARE_TOKEN", self.datasource.tushare_token)
        self.datasource.db_url = os.environ.get("DATABASE_URL", self.datasource.db_url)
        self.datasource.request_timeout = int(os.environ.get("API_TIMEOUT", self.datasource.request_timeout))

        # 缓存配置
        self.cache.redis_host = os.environ.get("REDIS_HOST", self.cache.redis_host)
        self.cache.redis_port = int(os.environ.get("REDIS_PORT", self.cache.redis_port))
        self.cache.redis_password = os.environ.get("REDIS_PASSWORD", self.cache.redis_password)

        # Web配置
        self.web.host = os.environ.get("WEB_HOST", self.web.host)
        self.web.port = int(os.environ.get("WEB_PORT", self.web.port))
        self.web.secret_key = os.environ.get("SECRET_KEY", self.web.secret_key)

        # 日志配置
        self.logging.level = os.environ.get("LOG_LEVEL", self.logging.level)
        self.logging.file_path = os.environ.get("LOG_FILE", self.logging.file_path)

    def get_cache_ttl(self, data_type: str) -> int:
        """获取指定数据类型的缓存TTL"""
        return self.cache.cache_ttl_config.get(data_type, self.cache.memory_cache_ttl)

    def is_market_trading_time(self, market: str = "SH") -> bool:
        """检查是否在交易时间内"""
        from datetime import datetime, time

        now = datetime.now().time()
        trading_hours = self.data.market_trading_hours.get(market, {})

        if not trading_hours:
            return False

        morning_start = time.fromisoformat(trading_hours["morning_start"])
        morning_end = time.fromisoformat(trading_hours["morning_end"])
        afternoon_start = time.fromisoformat(trading_hours["afternoon_start"])
        afternoon_end = time.fromisoformat(trading_hours["afternoon_end"])

        return (morning_start <= now <= morning_end) or (afternoon_start <= now <= afternoon_end)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "environment": self.environment.value,
            "api": self.api.__dict__,
            "cache": self.cache.__dict__,
            "data": self.data.__dict__,
            "logging": self.logging.__dict__,
            "web": self.web.__dict__,
        }


# 全局配置实例
config = StockQueryConfig(environment=Environment(os.environ.get("ENVIRONMENT", "development")))


# 便捷访问函数
def get_config() -> StockQueryConfig:
    """获取配置实例"""
    return config


def get_api_config() -> WebConfig:
    """获取API配置"""
    return config.web


def get_cache_config() -> CacheConfig:
    """获取缓存配置"""
    return config.cache


def get_data_config() -> DataConfig:
    """获取数据配置"""
    return config.data


def get_logging_config() -> LoggingConfig:
    """获取日志配置"""
    return config.logging


def get_web_config() -> WebConfig:
    """获取Web配置"""
    return config.web


if __name__ == "__main__":
    # 配置测试
    import json

    print("股票查询功能配置:")
    print(json.dumps(config.to_dict(), indent=2, ensure_ascii=False, default=str))

    print(f"\n当前是否在交易时间: {config.is_market_trading_time()}")
    print(f"实时行情缓存TTL: {config.get_cache_ttl('realtime_quote')}秒")
