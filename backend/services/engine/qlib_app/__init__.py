"""App 包初始化"""


def get_qlib_service():
    """获取 Qlib 服务实例"""
    from backend.services.engine.qlib_app.api.backtest import get_qlib_service_cached
    return get_qlib_service_cached()


def get_optimization_service():
    """获取优化服务实例"""
    from backend.services.engine.qlib_app.services.optimization_service import OptimizationService
    from backend.services.engine.qlib_app.services.backtest_service import QlibBacktestService
    backtest_service = QlibBacktestService()
    return OptimizationService(backtest_service)


def get_genetic_optimization_service():
    """获取遗传算法优化服务实例"""
    from backend.services.engine.qlib_app.services.genetic_optimization_service import GeneticOptimizationService
    from backend.services.engine.qlib_app.services.backtest_service import QlibBacktestService
    backtest_service = QlibBacktestService()
    return GeneticOptimizationService(backtest_service)


__all__ = [
    "get_qlib_service",
    "get_optimization_service",
    "get_genetic_optimization_service",
]
