"""市场适配器注册表"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import MarketAdapter

_registry: dict[str, type[MarketAdapter]] = {}


def register_adapter(cls: type[MarketAdapter]) -> type[MarketAdapter]:
    """装饰器：注册市场适配器"""
    _registry[cls.market_id] = cls
    return cls


def get_adapter(market_id: str) -> MarketAdapter:
    """获取市场适配器实例"""
    if market_id not in _registry:
        available = list(_registry.keys())
        raise ValueError(f"Unknown market: {market_id}. Available: {available}")
    return _registry[market_id]()


def list_markets() -> list[dict[str, str]]:
    """列出所有可用市场"""
    return [
        {
            "market_id": cls.market_id,
            "market_name": cls.market_name,
            "description": cls.description,
        }
        for cls in _registry.values()
    ]


# 导入适配器以触发注册
from . import a_share, crypto, hong_kong, us_stock  # noqa: F401, E402
