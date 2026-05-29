"""
策略模块
"""

from .base import BaseStrategy
from .simple_ma import SimpleMAStrategy

__all__ = [
    "BaseStrategy",
    "SimpleMAStrategy",
]
