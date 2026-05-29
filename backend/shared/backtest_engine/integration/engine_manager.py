"""
回测引擎管理器
统一管理事件驱动和向量化回测引擎
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Union

import pandas as pd

from ...data_operations.data_validator import DataValidator

try:
    from ...vectorized_backtest.engine import (
        VectorizedBacktestConfig,
        VectorizedBacktestEngine,
    )
except ImportError:  # pragma: no cover - optional dependency
    VectorizedBacktestConfig = None
    VectorizedBacktestEngine = None
from ..core.engine import BacktestEngine as EventDrivenEngine
from ..strategies.base import BaseStrategy
from .qlib_adapter import QlibBacktestAdapter, QlibNotAvailable

logger = logging.getLogger(__name__)


class EngineType(Enum):
    """回测引擎类型"""

    QLIB = "qlib"
    AUTO = "auto"  # 自动选择最适合的引擎


class BacktestEngineManager:
    """
    回测引擎管理器

    提供统一的接口来管理不同类型的回测引擎，
    自动选择最适合的引擎进行回测。
    """

    def __init__(self):
        """初始化回测引擎管理器"""
        self.logger = logging.getLogger(__name__)
        self.data_validator = DataValidator()
        self.current_engine = None
        self.current_engine_type = None
        self.engine_cache = {}
        # Qlib 适配器按需创建，避免未安装 pyqlib 时导入失败
        self._qlib_adapter: QlibBacktestAdapter | None = None

    def select_engine(
        self,
        data_size: int,
        strategy_type: str = "simple",
        complexity: str = "medium",
        performance_requirement: str = "standard",
    ) -> EngineType:
        """
        根据数据特征和需求自动选择最适合的回测引擎（现统一固定为 Qlib）

        Args:
            data_size: 数据大小（行数）
            strategy_type: 策略类型（simple, complex, portfolio）
            complexity: 复杂度（low, medium, high）
            performance_requirement: 性能要求（fast, standard, accurate）

        Returns:
            推荐的引擎类型
        """
        return EngineType.QLIB

    def create_event_driven_engine(
        self,
        initial_cash: float = 100000.0,
        commission_rate: float = 0.001,
        slippage_rate: float = 0.001,
        **kwargs,
    ) -> EventDrivenEngine:
        """创建事件驱动回测引擎"""
        engine = EventDrivenEngine(
            initial_cash=initial_cash,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
            **kwargs,
        )
        self.logger.info("创建事件驱动回测引擎")
        return engine

    def create_vectorized_engine(
        self,
        initial_capital: float = 100000.0,
        commission: float = 0.001,
        slippage: float = 0.0001,
        **kwargs,
    ) -> VectorizedBacktestEngine:
        """创建向量化回测引擎"""
        if VectorizedBacktestConfig is None or VectorizedBacktestEngine is None:
            raise ImportError("Vectorized backtest engine is not available")
        config = VectorizedBacktestConfig(
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage,
            **kwargs,
        )
        engine = VectorizedBacktestEngine(config)
        self.logger.info("创建向量化回测引擎")
        return engine

    def get_qlib_adapter(self, **kwargs) -> QlibBacktestAdapter:
        """惰性创建 Qlib 适配器，便于在未安装 pyqlib 的环境中降级"""
        if self._qlib_adapter is None:
            self._qlib_adapter = QlibBacktestAdapter(
                provider_uri=kwargs.get("provider_uri"),
                region=kwargs.get("region", "cn"),
                auto_init=kwargs.get("auto_init", True),
            )
        return self._qlib_adapter

    def run_backtest(
        self,
        data: pd.DataFrame,
        strategy: BaseStrategy | dict[str, Any],
        engine_type: EngineType | str = EngineType.AUTO,
        **kwargs,
    ) -> dict[str, Any]:
        """
        运行回测

        Args:
            data: 回测数据
            strategy: 策略实例或配置
            engine_type: 引擎类型
            **kwargs: 其他参数

        Returns:
            回测结果
        """
        try:
            # 选择引擎（仅支持 Qlib）
            if isinstance(engine_type, str):
                engine_type = EngineType(engine_type)

            if engine_type not in (EngineType.AUTO, EngineType.QLIB):
                raise ValueError("当前仅支持 Qlib 回测引擎")

            engine_type = EngineType.QLIB if engine_type == EngineType.AUTO else engine_type

            self.logger.info(f"使用 {engine_type.value} 引擎运行回测")

            # 运行回测
            return self._run_qlib_backtest(data, strategy, **kwargs)

        except Exception as e:
            self.logger.error(f"回测执行失败: {e}")
            raise

    def _run_event_driven_backtest(
        self,
        data: pd.DataFrame,
        strategy: BaseStrategy | dict[str, Any],
        **kwargs,
    ) -> dict[str, Any]:
        """运行事件驱动回测"""
        # 创建引擎
        engine = self.create_event_driven_engine(**kwargs)

        # 设置数据
        engine.set_data(data)

        # 添加策略
        if isinstance(strategy, BaseStrategy):
            engine.add_strategy(strategy)
        else:
            # 从配置创建策略
            strategy_instance = self._create_strategy_from_config(strategy)
            engine.add_strategy(strategy_instance)

        # 运行回测
        results = engine.run()

        # 添加元数据
        results["metadata"] = {
            "engine_type": "event_driven",
            "data_size": len(data),
            "execution_time": datetime.now().isoformat(),
            "strategy": strategy.name if hasattr(strategy, "name") else "unknown",
        }

        return results

    def _run_vectorized_backtest(
        self,
        data: pd.DataFrame,
        strategy: BaseStrategy | dict[str, Any],
        **kwargs,
    ) -> dict[str, Any]:
        """运行向量化回测"""
        # 创建引擎
        engine = self.create_vectorized_engine(**kwargs)

        # 生成信号
        if isinstance(strategy, BaseStrategy):
            signals = self._generate_signals_from_strategy(data, strategy)
        else:
            signals = self._generate_signals_from_config(data, strategy)

        # 运行回测
        result = engine.run_backtest(signals, data)

        # 转换结果格式
        results = {
            "success": result.success,
            "initial_cash": engine.config.initial_capital,
            "final_value": (result.equity_curve.iloc[-1] if len(result.equity_curve) > 0 else 0),
            "equity_curve": result.equity_curve.to_dict(),
            "positions": result.positions.to_dict(),
            "trades": result.trades.to_dict() if not result.trades.empty else {},
            "performance_metrics": result.performance_metrics,
            "risk_metrics": result.risk_metrics,
            "analysis": result.analysis,
            "metadata": {
                "engine_type": "vectorized",
                "data_size": len(data),
                "execution_time": datetime.now().isoformat(),
                "config": engine.config.__dict__,
            },
        }

        return results

    def _run_qlib_backtest(
        self,
        data: pd.DataFrame,
        strategy: BaseStrategy | dict[str, Any],
        **kwargs,
    ) -> dict[str, Any]:
        """
        运行 Qlib 回测

        说明：
        - 需要外部提供 Qlib strategy/executor 配置或实例（kwargs: qlib_strategy / qlib_executor）
        - 需要已准备好的 Qlib 数据或在环境变量 QLIB_PROVIDER_URI 指向的数据目录
        - 若 pyqlib 未安装或未初始化，将抛出 QlibNotAvailable，便于上层降级
        """
        qlib_strategy = kwargs.get("qlib_strategy")
        qlib_executor = kwargs.get("qlib_executor")
        if qlib_strategy is None or qlib_executor is None:
            raise ValueError("使用 Qlib 回测时必须提供 qlib_strategy 与 qlib_executor")

        codes = kwargs.get("codes")
        adapter = self.get_qlib_adapter(
            provider_uri=kwargs.get("provider_uri"),
            region=kwargs.get("region", "cn"),
            auto_init=kwargs.get("auto_init", True),
        )

        # Qlib 依赖自己的数据源，因此仅使用传入的开始/结束时间等元数据
        start_time = kwargs.get("start_time")
        end_time = kwargs.get("end_time")
        if start_time is None or end_time is None:
            raise ValueError("QLib 回测需要 start_time 与 end_time")

        try:
            portfolio_dict, indicator_dict = adapter.run_backtest(
                start_time=start_time,
                end_time=end_time,
                strategy=qlib_strategy,
                executor=qlib_executor,
                benchmark=kwargs.get("benchmark", "SH000300"),
                account=kwargs.get("account", kwargs.get("initial_cash", 1e9)),
                exchange_kwargs=kwargs.get("exchange_kwargs"),
                pos_type=kwargs.get("pos_type", "Position"),
                codes=codes,
            )
        except QlibNotAvailable as e:
            self.logger.error("Qlib 不可用: %s", e)
            raise

        return {
            "success": True,
            "portfolio": portfolio_dict,
            "indicators": indicator_dict,
            "metadata": {
                "engine_type": "qlib",
                "data_size": len(data),
                "execution_time": datetime.now().isoformat(),
                "provider_uri": adapter.provider_uri,
                "region": adapter.region,
            },
        }

    def _create_strategy_from_config(self, config: dict[str, Any]) -> BaseStrategy:
        """从配置创建策略实例"""
        # 这里可以根据配置创建不同的策略
        # 简化实现，返回一个默认策略
        from ..strategies.simple_ma import SimpleMAStrategy

        strategy_type = config.get("type", "simple_ma")
        params = config.get("parameters", {})

        if strategy_type == "simple_ma":
            return SimpleMAStrategy(**params)
        else:
            raise ValueError(f"不支持的策略类型: {strategy_type}")

    def _generate_signals_from_strategy(self, data: pd.DataFrame, strategy: BaseStrategy) -> pd.DataFrame:
        """从策略生成信号"""
        # 创建临时引擎来生成信号
        temp_engine = self.create_event_driven_engine()
        temp_engine.set_data(data)
        temp_engine.add_strategy(strategy)

        signals = []
        for i, (date, row) in enumerate(data.iterrows()):
            market_data = {
                "date": date,
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
            }

            # 模拟策略执行以生成信号
            strategy.on_data(market_data)

            # 简化的信号生成逻辑
            signal = 0
            if hasattr(strategy, "position") and strategy.position == 1:
                signal = 1
            elif hasattr(strategy, "position") and strategy.position == 0:
                signal = -1

            signals.append(signal)

        return pd.DataFrame({"signals": signals}, index=data.index)

    def _generate_signals_from_config(self, data: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
        """从配置生成信号"""
        strategy_type = config.get("type", "simple_ma")
        params = config.get("parameters", {})

        if strategy_type == "simple_ma":
            short_window = params.get("short_window", 5)
            long_window = params.get("long_window", 20)

            # 计算移动平均
            data["ma_short"] = data["close"].rolling(window=short_window).mean()
            data["ma_long"] = data["close"].rolling(window=long_window).mean()

            # 生成信号
            signals = []
            for i in range(len(data)):
                if pd.isna(data.iloc[i]["ma_short"]) or pd.isna(data.iloc[i]["ma_long"]):
                    signals.append(0)
                elif data.iloc[i]["ma_short"] > data.iloc[i]["ma_long"]:
                    signals.append(1)
                else:
                    signals.append(-1)

            return pd.DataFrame({"signals": signals}, index=data.index)
        else:
            raise ValueError(f"不支持的策略类型: {strategy_type}")

    def compare_engines(
        self,
        data: pd.DataFrame,
        strategy: BaseStrategy | dict[str, Any],
        **kwargs,
    ) -> dict[str, Any]:
        """
        比较不同引擎的回测结果

        Args:
            data: 回测数据
            strategy: 策略实例或配置
            **kwargs: 其他参数

        Returns:
            比较结果
        """
        results = {}

        # 运行事件驱动回测
        try:
            event_results = self._run_event_driven_backtest(data, strategy, **kwargs)
            results["event_driven"] = event_results
        except Exception as e:
            self.logger.error(f"事件驱动回测失败: {e}")
            results["event_driven"] = {"error": str(e)}

        # 运行向量化回测
        try:
            vectorized_results = self._run_vectorized_backtest(data, strategy, **kwargs)
            results["vectorized"] = vectorized_results
        except Exception as e:
            self.logger.error(f"向量化回测失败: {e}")
            results["vectorized"] = {"error": str(e)}

        # 添加比较分析
        results["comparison"] = self._compare_results(results)

        return results

    def _compare_results(self, results: dict[str, Any]) -> dict[str, Any]:
        """比较不同引擎的结果"""
        comparison = {"summary": {}, "differences": {}, "recommendations": []}

        if "event_driven" in results and "vectorized" in results:
            ed_result = results["event_driven"]
            vec_result = results["vectorized"]

            if "error" not in ed_result and "error" not in vec_result:
                # 比较关键指标
                metrics_to_compare = [
                    "total_return",
                    "annual_return",
                    "sharpe_ratio",
                    "max_drawdown",
                    "total_trades",
                ]

                for metric in metrics_to_compare:
                    ed_value = ed_result["performance_metrics"].get(metric, 0)
                    vec_value = vec_result["performance_metrics"].get(metric, 0)

                    comparison["differences"][metric] = {
                        "event_driven": ed_value,
                        "vectorized": vec_value,
                        "difference": abs(ed_value - vec_value),
                        "relative_diff": abs(ed_value - vec_value) / max(abs(ed_value), abs(vec_value), 1e-6),
                    }

                # 生成建议
                max_relative_diff = max(diff["relative_dif"] for diff in comparison["differences"].values())

                if max_relative_diff < 0.01:  # 小于1%差异
                    comparison["recommendations"].append("两种引擎结果高度一致，可以优先使用向量化引擎以获得更好的性能")
                elif max_relative_diff > 0.1:  # 大于10%差异
                    comparison["recommendations"].append("两种引擎结果差异较大，建议使用事件驱动引擎以获得更准确的结果")
                else:
                    comparison["recommendations"].append("两种引擎结果基本一致，可以根据性能需求选择合适的引擎")

        return comparison

    def get_engine_info(self) -> dict[str, Any]:
        """获取引擎信息"""
        return {
            "current_engine": (self.current_engine_type.value if self.current_engine_type else None),
            "supported_engines": [EngineType.QLIB.value],
            "cached_engines": list(self.engine_cache.keys()),
        }
