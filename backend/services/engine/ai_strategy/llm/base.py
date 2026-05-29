"""LLM Provider 抽象基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from collections.abc import AsyncGenerator

from ..models import (
    StrategyConversionRequest,
    StrategyConversionResponse,
    StrategyGenReq,
    StrategyGenRes,
)


class BaseLLMProvider(ABC):
    name: str = "base"
    supports_stream: bool = False

    @abstractmethod
    async def generate(self, req: StrategyGenReq) -> StrategyGenRes:
        """生成策略"""
        ...

    @abstractmethod
    async def convert(self, req: StrategyConversionRequest) -> StrategyConversionResponse:
        """转换策略"""
        ...

    @abstractmethod
    async def chat(self, messages: list, **kwargs) -> Any:
        """通用聊天接口"""
        ...

    async def generate_stream(self, req: StrategyGenReq) -> AsyncGenerator[str, None]:
        """流式生成策略"""
        raise NotImplementedError("generate_stream not implemented")

    async def chat_stream(self, req) -> AsyncGenerator[str, None]:
        """流式聊天对话"""
        raise NotImplementedError("chat_stream not implemented")


def normalize_name(desc: str) -> str:
    """规范化策略名称"""
    base = desc.strip().split("\n")[0][:32].replace(" ", "_") or "AutoStrategy"
    return "Auto_" + base
