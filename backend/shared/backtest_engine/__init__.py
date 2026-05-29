"""
QuantMind 统一回测引擎

提供高性能、可扩展的量化回测框架，支持多种策略类型、风险管理和性能分析。

主要模块:
- core: 核心回测引擎
- strategies: 策略基类和内置策略
- indicators: 技术指标库
- risk: 风险管理模块
- utils: 工具函数

Author: QuantMind Team
Version: 1.0.0
"""

from .core.data_feed import DataFeed
from .core.engine import BacktestEngine
from .core.portfolio import Portfolio

__version__ = "1.0.0"
__all__ = [
    "BacktestEngine",
    "Portfolio",
    "DataFeed",
]
