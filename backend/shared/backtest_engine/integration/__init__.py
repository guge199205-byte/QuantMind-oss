"""
回测引擎集成模块
提供统一的回测引擎接口和集成管理
"""

from .engine_manager import BacktestEngineManager
from .qlib_adapter import QlibBacktestAdapter, QlibNotAvailable
from .qlib_presets import build_default_qlib_executor, build_default_qlib_strategy

__all__ = [
    "BacktestEngineManager",
    "QlibBacktestAdapter",
    "QlibNotAvailable",
    "build_default_qlib_strategy",
    "build_default_qlib_executor",
]
