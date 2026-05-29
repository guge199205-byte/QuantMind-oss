"""Qlib API 依赖项。"""

from typing import Any

_qlib_service_cache = None


def get_qlib_service_cached() -> Any:
    global _qlib_service_cache
    if _qlib_service_cache is None:
        from backend.services.engine.qlib_app.services.backtest_service import (
            QlibBacktestService,
        )

        _qlib_service_cache = QlibBacktestService()
    return _qlib_service_cache


def get_qlib_service() -> Any:
    """依赖注入：获取 Qlib 服务实例。"""
    return get_qlib_service_cached()


def get_optimization_service() -> Any:
    """依赖注入：获取优化服务实例。"""
    from backend.services.engine.qlib_app import get_optimization_service as _factory

    return _factory()


def get_genetic_optimization_service() -> Any:
    """依赖注入：获取遗传算法优化服务实例。"""
    from backend.services.engine.qlib_app import get_genetic_optimization_service as _factory

    return _factory()
