#!/usr/bin/env python3
"""
QuantMind 统一配置管理器

整合所有服务的配置，提供统一的配置接口：
1. 环境变量配置
2. 数据库配置
3. API配置
4. 第三方服务配置
5. 安全配置
6. 日志配置

Author: QuantMind Team
Version: 1.0.0
"""

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class Environment(Enum):
    """环境类型枚举"""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class DatabaseConfig:
    """数据库配置"""

    # 通用配置
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 1800


@dataclass
class APIConfig:
    """API配置"""

    # 服务端口配置 (V2 Consolidated)
    api_service_port: int = 8000
    engine_service_port: int = 8001  # AI 策略、回测、推理
    trade_service_port: int = 8002  # 订单、持仓、撮合
    stream_service_port: int = 8003  # 行情、WebSocket

    # Legacy / Aliases for backward compatibility
    user_service_port: int = 8000
    ai_strategy_port: int = 8001
    backtest_port: int = 8001
    data_service_port: int = 8003
    market_data_port: int = 8003
    user_center_port: int = 8000
    stock_query_port: int = 8001

    # 通用API配置
    host: str = "0.0.0.0"
    debug: bool = True

    # CORS配置
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000", "http://localhost:3001"])

    # 第三方API密钥
    akshare_api_key: str = ""
    tongyi_qianwen_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # 其他数据源API
    ifind_refresh_token: str = ""
    alpha_vantage_api_key: str = ""
    juhe_api_key: str = ""

    @property
    def gateway_port(self) -> int:
        """Backward-compatible alias for legacy callers."""
        return self.api_service_port


@dataclass
class SecurityConfig:
    """安全配置"""

    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", ""))
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # JWT配置
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", os.getenv("JWT_SECRET_KEY", "")))
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30


@dataclass
class LoggingConfig:
    """日志配置"""

    level: str = "INFO"
    log_file: str | None = None
    max_log_size: int = 10485760  # 10MB
    backup_count: int = 5

    # 日志格式
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class MonitoringConfig:
    """监控配置"""

    enable_metrics: bool = True
    enable_tracing: bool = False

    # 性能监控
    enable_performance_monitoring: bool = True

    # 健康检查
    health_check_interval: int = 30  # 秒


class UnifiedConfigManager:
    """统一配置管理器"""

    def __init__(self, env_file: str | None = None):
        """
        初始化配置管理器

        Args:
            env_file: 环境变量文件路径
        """
        self.env_file = env_file or ".env"
        self.environment = self._detect_environment()
        self._load_config()

    def _detect_environment(self) -> Environment:
        """检测当前环境"""
        env = os.getenv("ENVIRONMENT", "development").lower()
        try:
            return Environment(env)
        except ValueError:
            logging.warning(f"Unknown environment: {env}, using development")
            return Environment.DEVELOPMENT

    def _load_config(self) -> None:
        """加载配置"""
        # 加载环境变量文件
        self._load_env_file()

        # 初始化各模块配置
        self.database = self._init_database_config()
        self.api = self._init_api_config()
        self.security = self._init_security_config()
        self.logging = self._init_logging_config()
        self.monitoring = self._init_monitoring_config()

        # 根据环境调整配置
        self._adjust_for_environment()

    def _load_env_file(self) -> None:
        """加载环境变量文件"""
        env_file = Path(self.env_file)
        if env_file.exists():
            try:
                with open(env_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            # 不覆盖运行时已注入的环境变量（例如本机脚本按服务注入的 Redis 主机）。
                            # 仅在缺失时使用 .env 补齐，避免导入副作用导致跨环境配置串改。
                            os.environ.setdefault(key, value.strip())
                logging.info(f"Loaded environment variables from {env_file}")
            except Exception as e:
                logging.warning(f"Failed to load env file {env_file}: {e}")

    def _init_database_config(self) -> DatabaseConfig:
        """初始化数据库配置"""
        return DatabaseConfig(
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
        )

    def _init_api_config(self) -> APIConfig:
        """初始化API配置"""
        # 解析CORS origins
        cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001")
        cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]

        return APIConfig(
            api_service_port=int(os.getenv("API_SERVICE_PORT", os.getenv("API_GATEWAY_PORT", "8000"))),
            user_service_port=int(os.getenv("USER_SERVICE_PORT", "8002")),
            ai_strategy_port=int(os.getenv("AI_STRATEGY_PORT", "8008")),
            backtest_port=int(os.getenv("BACKTEST_PORT", "8003")),
            data_service_port=int(os.getenv("DATA_SERVICE_PORT", "8012")),
            market_data_port=int(os.getenv("MARKET_DATA_PORT", "5002")),
            host=os.getenv("API_HOST", "127.0.0.1"),  # 默认localhost
            debug=os.getenv("DEBUG", "false").lower() == "true",
            cors_origins=cors_origins,
            # 第三方API密钥
            akshare_api_key=os.getenv("AKSHARE_API_KEY", ""),
            tongyi_qianwen_api_key=os.getenv("TONGYI_QIANWEN_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            google_api_key=os.getenv("GOOGLE_API_KEY", ""),
            ifind_refresh_token=os.getenv("IFIND_REFRESH_TOKEN", ""),
            alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY", ""),
            juhe_api_key=os.getenv("JUHE_API_KEY", ""),
        )

    def _init_security_config(self) -> SecurityConfig:
        """初始化安全配置"""
        return SecurityConfig(
            secret_key=os.getenv("SECRET_KEY", ""),
            algorithm=os.getenv("ALGORITHM", "HS256"),
            access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
            jwt_secret=os.getenv("JWT_SECRET", os.getenv("JWT_SECRET_KEY", "")),
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            jwt_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "30")),
        )

    def _init_logging_config(self) -> LoggingConfig:
        """初始化日志配置"""
        return LoggingConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE"),
            max_log_size=int(os.getenv("MAX_LOG_SIZE", "10485760")),
            backup_count=int(os.getenv("BACKUP_COUNT", "5")),
        )

    def _init_monitoring_config(self) -> MonitoringConfig:
        """初始化监控配置"""
        return MonitoringConfig(
            enable_metrics=os.getenv("ENABLE_METRICS", "true").lower() == "true",
            enable_tracing=os.getenv("ENABLE_TRACING", "false").lower() == "true",
            enable_performance_monitoring=os.getenv("ENABLE_PERFORMANCE_MONITORING", "true").lower() == "true",
            health_check_interval=int(os.getenv("HEALTH_CHECK_INTERVAL", "30")),
        )

    def _adjust_for_environment(self) -> None:
        """根据环境调整配置"""
        if self.environment == Environment.PRODUCTION:
            self.api.debug = False
            self.logging.level = "WARNING"
            self.monitoring.enable_tracing = True
        elif self.environment == Environment.TESTING:
            self.api.debug = False
            self.logging.level = "DEBUG"
            self.monitoring.enable_metrics = False

    def get_database_url(self, db_type: str | None = None) -> str:
        """获取数据库连接URL"""
        raise NotImplementedError(
            "Legacy database configuration removed. Use backend.shared.database_manager_v2 instead."
        )

    def get_service_config(self, service_name: str) -> dict[str, Any]:
        """获取特定服务的配置"""
        service_configs = {
            "api_service": {
                "port": self.api.api_service_port,
                "host": self.api.host,
                "debug": self.api.debug,
                "database_url": self.get_database_url(),
            },
            "user_service": {
                "port": self.api.user_service_port,
                "host": self.api.host,
                "database_url": self.get_database_url(),
                "jwt_secret": self.security.jwt_secret,
                "jwt_expire_minutes": self.security.jwt_expire_minutes,
            },
            "ai_strategy": {
                "port": self.api.ai_strategy_port,
                "host": self.api.host,
                "openai_api_key": self.api.openai_api_key,
                "tongyi_qianwen_api_key": self.api.tongyi_qianwen_api_key,
                "anthropic_api_key": self.api.anthropic_api_key,
                "google_api_key": self.api.google_api_key,
            },
            "data_service": {
                "port": self.api.data_service_port,
                "host": self.api.host,
                "database_url": self.get_database_url(),
                "akshare_api_key": self.api.akshare_api_key,
            },
            "market_data": {
                "port": self.api.market_data_port,
                "host": self.api.host,
                "database_url": self.get_database_url(),
                "ifind_token": self.api.ifind_refresh_token,
            },
        }

        # Backward compatibility for legacy service key.
        service_configs["api_gateway"] = service_configs["api_service"]

        return service_configs.get(service_name, {})

    def export_config(self, config_path: str | None = None) -> dict[str, Any]:
        """导出完整配置"""
        config_path = config_path or f"config_export_{self.environment.value}.json"

        config = {
            "environment": self.environment.value,
            "database": self.database.__dict__,
            "api": self.api.__dict__,
            "security": self.security.__dict__,
            "logging": self.logging.__dict__,
            "monitoring": self.monitoring.__dict__,
        }

        # 移除敏感信息
        sanitized_config = self._sanitize_config(config)

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(sanitized_config, f, indent=2, ensure_ascii=False)
            logging.info(f"Configuration exported to {config_path}")
        except Exception as e:
            logging.error(f"Failed to export configuration: {e}")

        return sanitized_config

    def _sanitize_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """清理配置中的敏感信息"""
        sensitive_keys = ["secret_key", "password", "api_key", "token", "jwt_secret"]

        def sanitize_dict(d: dict[str, Any]) -> dict[str, Any]:
            result = {}
            for key, value in d.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    result[key] = "***HIDDEN***" if value else ""
                elif isinstance(value, dict):
                    result[key] = sanitize_dict(value)
                elif isinstance(value, list):
                    result[key] = [sanitize_dict(item) if isinstance(item, dict) else item for item in value]
                else:
                    result[key] = value
            return result

        return sanitize_dict(config)


# 全局配置实例
config_manager = UnifiedConfigManager()


# 提供便捷访问
def get_config() -> UnifiedConfigManager:
    """获取全局配置管理器实例"""
    return config_manager


def get_database_url(db_type: str | None = None) -> str:
    """获取数据库URL"""
    return config_manager.get_database_url(db_type)


def get_service_config(service_name: str) -> dict[str, Any]:
    """获取服务配置"""
    return config_manager.get_service_config(service_name)


if __name__ == "__main__":
    # 测试配置管理器
    config = get_config()

    print(f"Environment: {config.environment.value}")
    print(f"API Service Port: {config.api.api_service_port}")
    print(f"Debug Mode: {config.api.debug}")
    print(f"Log Level: {config.logging.level}")

    # 导出配置（用于调试）
    config.export_config()
