"""API配置管理"""

import os

try:
    from .llm_config_loader import LLMConfigLoader

    _llm_config_available = True
except ImportError:
    _llm_config_available = False

# 传统API配置字典（保持向后兼容）
api_config: dict[str, str] = {
    "tsanghi": os.getenv("TSANGHI_API_KEY", ""),
    "qwen": os.getenv("QWEN_API_KEY", ""),
    "gemini": os.getenv("GEMINI_API_KEY", ""),
    "openai": os.getenv("OPENAI_API_KEY", ""),
    "claude": os.getenv("CLAUDE_API_KEY", ""),
    "baidu": os.getenv("BAIDU_API_KEY", ""),
    "zhipu": os.getenv("ZHIPU_API_KEY", ""),
    "alpha_vantage": os.getenv("ALPHA_VANTAGE_API_KEY", ""),
    "juhe": os.getenv("JUHE_API_KEY", ""),
    "canghai": os.getenv("CANGHAI_API_KEY", ""),
}

# LLM配置加载器实例（延迟初始化）
_llm_loader = None


def get_llm_loader():
    """获取LLM配置加载器实例"""
    global _llm_loader
    if _llm_loader is None and _llm_config_available:
        try:
            _llm_loader = LLMConfigLoader()
            _llm_loader.load_all_configs()
        except Exception as e:
            print(f"警告: 无法加载LLM配置: {e}")
            _llm_loader = None
    return _llm_loader


def get_api_key(service: str) -> str | None:
    """获取指定服务的API密钥

    优先从新的LLM配置系统获取，如果不可用则使用传统配置
    """
    # 首先尝试从新的LLM配置系统获取
    if _llm_config_available and service in [
        "qwen",
        "gemini",
        "openai",
        "claude",
        "baidu",
        "zhipu",
        "deepseek",
    ]:
        loader = get_llm_loader()
        if loader:
            config = loader.api_manager.get_config(service)
            if config and config.api_key:
                return config.api_key

    # 回退到传统配置
    return api_config.get(service)


def set_api_key(service: str, key: str) -> None:
    """设置指定服务的API密钥

    同时更新传统配置和新的LLM配置系统
    """
    # 更新传统配置
    api_config[service] = key

    # 更新新的LLM配置系统
    if _llm_config_available and service in [
        "qwen",
        "gemini",
        "openai",
        "claude",
        "baidu",
        "zhipu",
        "deepseek",
    ]:
        loader = get_llm_loader()
        if loader:
            loader.api_manager.set_api_key(service, key)


def get_llm_configs() -> dict[str, dict]:
    """获取所有LLM配置信息"""
    if not _llm_config_available:
        return {}

    loader = get_llm_loader()
    if not loader:
        return {}

    return loader.get_config_status()


def get_enabled_llm_providers() -> list:
    """获取启用的LLM提供商列表"""
    if not _llm_config_available:
        return []

    loader = get_llm_loader()
    if not loader:
        return []

    enabled_configs = loader.api_manager.get_enabled_configs()
    return list(enabled_configs.keys())


def get_primary_llm_provider() -> str | None:
    """获取主要（优先级最高）的LLM提供商"""
    if not _llm_config_available:
        return None

    loader = get_llm_loader()
    if not loader:
        return None

    configs = loader.api_manager.get_configs_by_priority()
    return configs[0].provider if configs else None
