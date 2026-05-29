from __future__ import annotations

import os
from pathlib import Path
from typing import Dict
from collections.abc import Callable

from dotenv import load_dotenv

from .providers.base import BaseLLMProvider

REGISTRY: dict[str, Callable[[], BaseLLMProvider]] = {}

# 加载项目根目录的 .env。
# 重要：不要覆盖运行时环境变量（运行时 env > .env），否则会导致诸如 LLM_PROVIDER
# 这类开关在启动命令里设置后仍被 .env 覆盖。
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

# 注册 Qwen 提供商
try:
    from .llm.qwen import QwenProvider as QwenLLMProvider

    REGISTRY["qwen"] = QwenLLMProvider
except Exception as e:
    print(f"Warning: Failed to load Qwen provider: {e}")

_provider_cache: dict[str, BaseLLMProvider] = {}

# 注册 DeepSeek 提供商
try:
    from .llm.deepseek import DeepseekProvider as DeepseekLLMProvider

    REGISTRY["deepseek"] = DeepseekLLMProvider
except Exception as e:
    print(f"Warning: Failed to load DeepSeek provider: {e}")


def get_provider_name() -> str:
    """获取当前配置的提供商名称"""
    return (os.getenv("LLM_PROVIDER") or "qwen").strip().lower()


def get_provider(name: str | None = None) -> BaseLLMProvider:
    """获取 LLM 提供商实例"""
    provider_name = name or get_provider_name()

    if provider_name not in _provider_cache:
        factory = REGISTRY.get(provider_name)
        if not factory:
            # 如果请求的提供商不存在，回退到第一个可用的提供商
            if not REGISTRY:
                raise RuntimeError("No LLM providers registered")
            provider_name = next(iter(REGISTRY.keys()))
            factory = REGISTRY[provider_name]

        _provider_cache[provider_name] = factory()

    return _provider_cache[provider_name]
