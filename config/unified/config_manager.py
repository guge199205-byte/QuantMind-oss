#!/usr/bin/env python3
"""
QuantMind统一配置管理器
提供配置加载、验证和环境变量替换功能
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ServiceConfig:
    """服务配置数据类"""

    name: str
    display_name: str
    version: str
    description: str
    port: int
    config: dict[str, Any] = field(default_factory=dict)


class ConfigManager:
    """统一配置管理器"""

    def __init__(self, config_dir: str | None = None):
        """
        初始化配置管理器

        Args:
            config_dir: 配置目录路径，默认为当前目录下的config/unified
        """
        if config_dir is None:
            # 获取脚本所在目录的config/unified
            script_dir = Path(__file__).parent
            self.config_dir = script_dir
        else:
            self.config_dir = Path(config_dir)

        self.environment = os.getenv("ENVIRONMENT", "development")
        self.logger = self._setup_logger()
        self._config_cache = {}

        self.logger.info(
            f"ConfigManager initialized with environment: {self.environment}"
        )
        self.logger.info(f"Config directory: {self.config_dir}")

    def _setup_logger(self) -> logging.Logger:
        """设置配置管理器专用日志器"""
        logger = logging.getLogger("config_manager")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _load_yaml_file(self, file_path: Path) -> dict[str, Any]:
        """加载YAML文件"""
        try:
            if file_path.exists():
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                    # 环境变量替换
                    content = self._substitute_env_vars(content)
                    return yaml.safe_load(content) or {}
            else:
                self.logger.warning(f"Config file not found: {file_path}")
                return {}
        except Exception as e:
            self.logger.error(f"Failed to load config file {file_path}: {e}")
            return {}

    def _substitute_env_vars(self, content: str) -> str:
        """替换配置文件中的环境变量"""
        # 支持 ${VAR:default} 格式
        pattern = r"\$\{([^}]+)\}"

        def replacer(match):
            var_expr = match.group(1)
            if ":" in var_expr:
                var_name, default_value = var_expr.split(":", 1)
                return os.getenv(var_name.strip(), default_value.strip())
            else:
                return os.getenv(var_expr.strip(), "")

        return re.sub(pattern, replacer, content)

    def _get_config_file_path(self, config_type: str, name: str) -> Path:
        """获取配置文件路径"""
        return self.config_dir / config_type / f"{name}.yaml"

    def load_shared_config(self) -> dict[str, Any]:
        """加载共享配置"""
        cache_key = "shared"
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]

        shared_dir = self.config_dir / "shared"
        shared_config = {}

        if shared_dir.exists():
            for config_file in shared_dir.glob("*.yaml"):
                config_name = config_file.stem
                config_data = self._load_yaml_file(config_file)
                shared_config[config_name] = config_data
                self.logger.debug(f"Loaded shared config: {config_name}")

        self._config_cache[cache_key] = shared_config
        return shared_config

    def load_environment_config(self) -> dict[str, Any]:
        """加载环境配置"""
        cache_key = f"env_{self.environment}"
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]

        env_file = self._get_config_file_path("environments", self.environment)
        env_config = self._load_yaml_file(env_file)

        self._config_cache[cache_key] = env_config
        self.logger.info(f"Loaded environment config: {self.environment}")
        return env_config

    def load_service_config(self, service_name: str) -> dict[str, Any]:
        """加载服务配置"""
        cache_key = f"service_{service_name}"
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]

        service_file = self._get_config_file_path("services", service_name)
        service_config = self._load_yaml_file(service_file)

        self._config_cache[cache_key] = service_config
        self.logger.info(f"Loaded service config: {service_name}")
        return service_config

    def get_merged_config(self, service_name: str | None = None) -> dict[str, Any]:
        """获取合并后的配置

        配置合并优先级：
        1. 共享配置 (shared/*.yaml)
        2. 环境配置 (environments/{env}.yaml)
        3. 服务配置 (services/{service}.yaml)
        """
        # 加载共享配置
        merged_config = {}
        shared_config = self.load_shared_config()
        for category, config in shared_config.items():
            if isinstance(config, dict):
                merged_config.update(config)

                # 加载环境配置并合并
        env_config = self.load_environment_config()
        merged_config = self._deep_merge(merged_config, env_config)

        # 加载服务配置并合并
        if service_name:
            service_config = self.load_service_config(service_name)
            merged_config = self._deep_merge(merged_config, service_config)

        return merged_config

    def _deep_merge(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """深度合并字典"""
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def get_database_config(self) -> dict[str, Any]:
        """获取数据库配置"""
        config = self.get_merged_config()
        return config.get("database", {})

    def get_service_config(self, service_name: str) -> ServiceConfig:
        """获取服务配置"""
        merged_config = self.get_merged_config(service_name)
        service_info = merged_config.get("service", {})

        return ServiceConfig(
            name=service_info.get("name", service_name),
            display_name=service_info.get("display_name", service_name),
            version=service_info.get("version", "1.0.0"),
            description=service_info.get("description", ""),
            port=service_info.get("port", 8000),
            config=merged_config,
        )

    def get_logging_config(self) -> dict[str, Any]:
        """获取日志配置"""
        config = self.get_merged_config()
        return config.get("logging", {})

    def get_security_config(self) -> dict[str, Any]:
        """获取安全配置"""
        config = self.get_merged_config()
        return config.get("security", {})

    def validate_config(self, service_name: str | None = None) -> list[str]:
        """验证配置有效性"""
        errors = []
        config = self.get_merged_config(service_name)

        # 验证必需的配置项
        if "database" not in config:
            errors.append("Missing database configuration")

        if "security" not in config:
            errors.append("Missing security configuration")

            # 验证数据库配置
        db_config = config.get("database", {})
        db_type = db_config.get("type")
        if db_type == "postgresql":
            required_pg_fields = ["host", "port", "database", "username", "password"]
            for req_field in required_pg_fields:
                if not db_config.get("postgresql", {}).get(req_field):
                    errors.append(
                        f"PostgreSQL database missing required field: {req_field}"
                    )

        # 验证服务配置
        if service_name:
            service_config = config.get("service", {})
            if not service_config.get("port"):
                errors.append(
                    f"Service {service_name} missing port configuration")

        return errors

    def reload_config(self):
        """重新加载配置"""
        self._config_cache.clear()
        self.logger.info("Configuration cache cleared")

    def list_available_services(self) -> list[str]:
        """列出可用的服务配置"""
        services_dir = self.config_dir / "services"
        if services_dir.exists():
            return [f.stem for f in services_dir.glob("*.yaml")]
        return []

    def list_available_environments(self) -> list[str]:
        """列出可用的环境配置"""
        env_dir = self.config_dir / "environments"
        if env_dir.exists():
            return [f.stem for f in env_dir.glob("*.yaml")]
        return []


def main():
    """命令行工具入口"""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="QuantMind配置管理工具")
    parser.add_argument("--service", "-s", help="服务名称")
    parser.add_argument("--environment", "-e", help="环境名称")
    parser.add_argument("--list-services", action="store_true", help="列出可用服务")
    parser.add_argument("--list-environments",
                        action="store_true", help="列出可用环境")
    parser.add_argument("--validate", action="store_true", help="验证配置")
    parser.add_argument(
        "--output", "-o", choices=["yaml", "json"], default="yaml", help="输出格式"
    )

    args = parser.parse_args()

    # 设置环境
    if args.environment:
        os.environ["ENVIRONMENT"] = args.environment

        # 创建配置管理器
    config_manager = ConfigManager()

    if args.list_services:
        services = config_manager.list_available_services()
        print("Available services:")
        for service in services:
            print(f"  - {service}")
        return

    if args.list_environments:
        environments = config_manager.list_available_environments()
        print("Available environments:")
        for env in environments:
            print(f"  - {env}")
        return

        # 获取配置
    config = config_manager.get_merged_config(args.service)

    # 验证配置
    if args.validate:
        errors = config_manager.validate_config(args.service)
        if errors:
            print("Configuration validation failed:")
            for error in errors:
                print(f"  - {error}")
            return 1
        else:
            print("Configuration validation passed")

            # 输出配置
    if args.output == "json":
        print(json.dumps(config, indent=2, ensure_ascii=False))
    else:
        print(yaml.dump(config, default_flow_style=False, allow_unicode=True))

    return 0


if __name__ == "__main__":
    exit(main())
