"""
Qlib 策略/执行器预设，避免重复拼装默认配置
"""

from __future__ import annotations

from typing import Any, Dict

from .qlib_adapter import QlibNotAvailable


def build_default_qlib_strategy(params: dict[str, Any]) -> Any:
    """
    返回一个 Qlib 策略实例
    支持 TopkDropoutStrategy 和 WeightStrategy
    """
    strategy_type = params.get("qlib_strategy_type", "TopkDropout")

    try:
        topk = int(params.get("topk", 10))
        n_drop = int(params.get("n_drop", max(1, round(topk * 0.2))))
        if strategy_type == "TopkDropout":
            from qlib.contrib.strategy import TopkDropoutStrategy

            return TopkDropoutStrategy(
                topk=topk,
                n_drop=n_drop,
                # signal_source parameter removed as it's not standard Qlib TopkDropoutStrategy arg
                # If needed, it should be passed via kwargs or config
            )
        elif strategy_type == "WeightStrategy":
            from qlib.contrib.strategy import WeightStrategy

            return WeightStrategy()
        else:
            # Default fallback
            from qlib.contrib.strategy import TopkDropoutStrategy

            return TopkDropoutStrategy(
                topk=topk,
                n_drop=n_drop,
            )

    except ImportError as e:  # noqa: BLE001
        raise QlibNotAvailable(f"pyqlib 未安装或策略 {strategy_type} 无法加载") from e


def build_default_qlib_executor(params: dict[str, Any]) -> Any:
    """
    返回一个默认 Qlib 执行器（SimulatorExecutor，日频）
    """
    try:
        from qlib.backtest.executor import SimulatorExecutor
    except ImportError as e:  # noqa: BLE001
        raise QlibNotAvailable("pyqlib 未安装，无法构建 Qlib 执行器") from e

    return SimulatorExecutor(
        time_per_step=params.get("time_per_step", "day"),
        generate_portfolio_metrics=True,
        verbose=False,
        indicator_config={},
    )


__all__ = ["build_default_qlib_strategy", "build_default_qlib_executor"]
