"""
AI Provider统一抽象层

提供统一的AI服务接口，支持多个AI Provider：
- OpenAI (GPT-3.5, GPT-4)
- Anthropic Claude
- DeepSeek
- 本地模型 (Ollama, LocalAI)
"""

from .base import BaseAIProvider, StrategyRequest, StrategyResponse
from .claude_provider import ClaudeProvider
from .deepseek_provider import DeepSeekProvider
from .factory import AIProviderFactory
from .local_provider import LocalProvider
from .openai_provider import OpenAIProvider
from .strategy_optimizer import StrategyOptimizer

__all__ = [
    "BaseAIProvider",
    "StrategyRequest",
    "StrategyResponse",
    "OpenAIProvider",
    "ClaudeProvider",
    "DeepSeekProvider",
    "LocalProvider",
    "AIProviderFactory",
    "StrategyOptimizer",
]
