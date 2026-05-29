"""
AI Provider工厂类
"""

from typing import Dict, List, Optional, Type

from ..config import get_config
from .base import BaseAIProvider, ModelConfig, ModelType
from .claude_provider import ClaudeProvider
from .deepseek_provider import DeepSeekProvider
from .local_provider import LocalProvider
from .openai_provider import OpenAIProvider


class AIProviderFactory:
    """AI Provider工厂类"""

    _providers: dict[str, type[BaseAIProvider]] = {}
    _instances: dict[str, BaseAIProvider] = {}

    @classmethod
    def register_provider(cls, name: str, provider_class: type[BaseAIProvider]) -> None:
        """注册AI Provider"""
        cls._providers[name] = provider_class

    @classmethod
    def create_provider(cls, provider_name: str, config: ModelConfig | None = None) -> BaseAIProvider:
        """创建AI Provider实例"""
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown provider: {provider_name}")

        if config is None:
            config = cls._get_default_config(provider_name)

        provider_class = cls._providers[provider_name]
        return provider_class(config)

    @classmethod
    def get_provider(cls, provider_name: str, config: ModelConfig | None = None) -> BaseAIProvider:
        """获取AI Provider实例（单例模式）"""
        key = f"{provider_name}_{id(config) if config else 'default'}"

        if key not in cls._instances:
            cls._instances[key] = cls.create_provider(provider_name, config)

        return cls._instances[key]

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """获取可用的Provider列表"""
        return list(cls._providers.keys())

    @classmethod
    def get_supported_models(cls, provider_name: str) -> list[ModelType]:
        """获取指定Provider支持的模型"""
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown provider: {provider_name}")

        provider_class = cls._providers[provider_name]
        temp_instance = provider_class(ModelConfig(model_name="temp", model_type=ModelType.CUSTOM))
        return temp_instance.get_supported_models()

    @classmethod
    def _get_default_config(cls, provider_name: str) -> ModelConfig:
        """获取默认配置"""
        try:
            config_manager = get_config()
            ai_config = config_manager.get("ai_providers", {})
            provider_config = ai_config.get(provider_name, {})

            return ModelConfig(
                model_name=provider_config.get("model_name", "default"),
                model_type=ModelType(provider_config.get("model_type", "custom")),
                api_key=provider_config.get("api_key"),
                api_base=provider_config.get("api_base"),
                max_tokens=provider_config.get("max_tokens", 4000),
                temperature=provider_config.get("temperature", 0.7),
                timeout=provider_config.get("timeout", 60),
                retry_attempts=provider_config.get("retry_attempts", 3),
                custom_params=provider_config.get("custom_params", {}),
            )
        except Exception:
            # 返回最基本的配置
            return ModelConfig(model_name="default", model_type=ModelType.CUSTOM)

    @classmethod
    async def initialize_all_providers(cls) -> dict[str, bool]:
        """初始化所有注册的Provider"""
        results = {}

        for provider_name in cls._providers:
            try:
                provider = cls.get_provider(provider_name)
                success = await provider.initialize()
                results[provider_name] = success
            except Exception as e:
                results[provider_name] = False
                print(f"Failed to initialize {provider_name}: {e}")

        return results

    @classmethod
    async def health_check_all(cls) -> dict[str, dict]:
        """检查所有Provider的健康状态"""
        results = {}

        for key, provider in cls._instances.items():
            try:
                health = await provider.health_check()
                results[key] = health
            except Exception as e:
                results[key] = {
                    "provider": provider.__class__.__name__,
                    "status": "error",
                    "error": str(e),
                }

        return results


# 注册所有Provider
def register_default_providers():
    """注册默认的AI Provider"""
    AIProviderFactory.register_provider("openai", OpenAIProvider)
    AIProviderFactory.register_provider("claude", ClaudeProvider)
    AIProviderFactory.register_provider("deepseek", DeepSeekProvider)
    AIProviderFactory.register_provider("local", LocalProvider)


# 自动注册默认Provider
register_default_providers()
