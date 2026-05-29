"""
策略优化器
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

from ..observability.logging import get_logger
from .base import BaseAIProvider, StrategyParameter, StrategyResponse

logger = get_logger(__name__)


class OptimizationMetric(Enum):
    """优化指标"""

    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    TOTAL_RETURN = "total_return"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    CALMAR_RATIO = "calmar_ratio"
    SORTINO_RATIO = "sortino_ratio"


@dataclass
class OptimizationTarget:
    """优化目标"""

    metric: OptimizationMetric
    weight: float = 1.0
    target_value: float | None = None
    minimize: bool = False  # 是否要最小化该指标


@dataclass
class OptimizationResult:
    """优化结果"""

    best_parameters: dict[str, Any]
    best_score: float
    optimization_history: list[dict[str, Any]] = field(default_factory=list)
    metric_scores: dict[str, float] = field(default_factory=dict)
    optimization_time: float = 0.0
    iterations: int = 0


class StrategyOptimizer:
    """策略优化器"""

    def __init__(self, ai_provider: BaseAIProvider):
        self.ai_provider = ai_provider
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    async def optimize_parameters(
        self,
        strategy_response: StrategyResponse,
        historical_data: dict[str, Any],
        optimization_targets: list[OptimizationTarget],
        max_iterations: int = 10,
    ) -> OptimizationResult:
        """优化策略参数"""
        start_time = time.time()

        self.logger.info(
            "Starting strategy parameter optimization",
            strategy=strategy_response.strategy_name,
            parameters=len(strategy_response.parameters),
            targets=[t.metric.value for t in optimization_targets],
        )

        best_result = None
        best_score = float("-in") if not optimization_targets[0].minimize else float("inf")
        optimization_history = []

        # 初始参数
        current_parameters = {p.name: p.default_value for p in strategy_response.parameters}

        for iteration in range(max_iterations):
            self.logger.debug(f"Optimization iteration {iteration + 1}/{max_iterations}")

            # 生成参数变体
            parameter_variants = self._generate_parameter_variants(
                strategy_response.parameters, current_parameters, iteration
            )

            # 并行测试参数组合
            tasks = []
            for variant in parameter_variants:
                task = self._test_parameters(strategy_response, variant, historical_data, optimization_targets)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 找到最佳结果
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.warning(f"Parameter test failed: {result}")
                    continue

                score = self._calculate_composite_score(result["metric_scores"], optimization_targets)

                optimization_history.append(
                    {
                        "iteration": iteration + 1,
                        "parameters": result["parameters"],
                        "score": score,
                        "metric_scores": result["metric_scores"],
                    }
                )

                # 更新最佳结果
                if (not optimization_targets[0].minimize and score > best_score) or (
                    optimization_targets[0].minimize and score < best_score
                ):
                    best_score = score
                    best_result = result
                    current_parameters = result["parameters"]

            # 使用AI优化参数
            if iteration < max_iterations - 1:
                try:
                    ai_suggestion = await self._get_ai_optimization_suggestion(
                        strategy_response,
                        current_parameters,
                        optimization_history[-5:],  # 最近5次结果
                        optimization_targets,
                    )

                    if ai_suggestion:
                        current_parameters.update(ai_suggestion)
                        self.logger.debug("Applied AI optimization suggestion")

                except Exception as e:
                    self.logger.warning(f"AI optimization failed: {e}")

        optimization_time = time.time() - start_time

        final_result = OptimizationResult(
            best_parameters=(best_result["parameters"] if best_result else current_parameters),
            best_score=best_score,
            optimization_history=optimization_history,
            metric_scores=best_result["metric_scores"] if best_result else {},
            optimization_time=optimization_time,
            iterations=max_iterations,
        )

        self.logger.info(
            "Strategy optimization completed",
            best_score=best_score,
            iterations=max_iterations,
            time=optimization_time,
        )

        return final_result

    async def optimize_strategy_logic(
        self,
        strategy_response: StrategyResponse,
        performance_issues: list[str],
        optimization_goals: list[str],
    ) -> StrategyResponse:
        """优化策略逻辑"""
        self.logger.info(
            "Starting strategy logic optimization",
            strategy=strategy_response.strategy_name,
            issues=len(performance_issues),
            goals=len(optimization_goals),
        )

        try:
            optimized_response = await self.ai_provider.optimize_strategy(
                strategy_response.code.code,
                {"issues": performance_issues, "goals": optimization_goals},
                optimization_goals,
            )

            self.logger.info(
                "Strategy logic optimization completed",
                confidence=optimized_response.confidence_score,
            )

            return optimized_response

        except Exception as e:
            self.logger.error(f"Strategy logic optimization failed: {e}")
            raise

    def _generate_parameter_variants(
        self,
        parameters: list[StrategyParameter],
        current_params: dict[str, Any],
        iteration: int,
    ) -> list[dict[str, Any]]:
        """生成参数变体"""
        variants = []

        # 基于迭代次数调整探索范围
        exploration_factor = max(0.1, 1.0 - (iteration / 10))

        for param in parameters:
            if param.range is None:
                continue

            param_variants = []
            base_value = current_params[param.name]

            if param.type == "float":
                min_val = param.range.get("min", 0)
                max_val = param.range.get("max", 1)
                step = param.range.get("step", 0.1)

                # 生成3个变体
                for offset in [-step, 0, step]:
                    new_value = base_value + offset * exploration_factor
                    new_value = max(min_val, min(max_val, new_value))

                    variant = current_params.copy()
                    variant[param.name] = new_value
                    param_variants.append(variant)

            elif param.type == "int":
                min_val = param.range.get("min", 0)
                max_val = param.range.get("max", 100)
                step = param.range.get("step", 1)

                for offset in [-step, 0, step]:
                    new_value = base_value + offset * exploration_factor
                    new_value = int(max(min_val, min(max_val, new_value)))

                    variant = current_params.copy()
                    variant[param.name] = new_value
                    param_variants.append(variant)

        # 添加当前参数作为基准
        variants.append(current_params)

        # 随机选择一些变体进行测试
        import random

        max_variants = min(10, len(variants))
        selected_variants = random.sample(variants, max_variants) if len(variants) > max_variants else variants

        return selected_variants

    async def _test_parameters(
        self,
        strategy_response: StrategyResponse,
        parameters: dict[str, Any],
        historical_data: dict[str, Any],
        optimization_targets: list[OptimizationTarget],
    ) -> dict[str, Any]:
        """测试参数组合"""
        # 这里应该调用回测引擎进行测试
        # 为了演示，我们模拟回测结果

        await asyncio.sleep(0.1)  # 模拟回测时间

        # 模拟性能指标
        metric_scores = {}
        for target in optimization_targets:
            if target.metric == OptimizationMetric.SHARPE_RATIO:
                # 基于参数生成模拟的Sharpe比率
                metric_scores[target.metric.value] = np.random.normal(1.2, 0.3)
            elif target.metric == OptimizationMetric.MAX_DRAWDOWN:
                metric_scores[target.metric.value] = np.random.uniform(0.05, 0.25)
            elif target.metric == OptimizationMetric.TOTAL_RETURN:
                metric_scores[target.metric.value] = np.random.uniform(0.1, 0.5)
            elif target.metric == OptimizationMetric.WIN_RATE:
                metric_scores[target.metric.value] = np.random.uniform(0.4, 0.7)

        return {"parameters": parameters, "metric_scores": metric_scores}

    def _calculate_composite_score(
        self,
        metric_scores: dict[str, float],
        optimization_targets: list[OptimizationTarget],
    ) -> float:
        """计算综合评分"""
        total_score = 0.0
        total_weight = 0.0

        for target in optimization_targets:
            metric_value = metric_scores.get(target.metric.value, 0.0)
            weight = target.weight

            if target.minimize:
                # 对于要最小化的指标，取倒数
                score = weight / (1.0 + metric_value) if metric_value > 0 else weight
            else:
                score = weight * metric_value

            total_score += score
            total_weight += weight

        return total_score / total_weight if total_weight > 0 else 0.0

    async def _get_ai_optimization_suggestion(
        self,
        strategy_response: StrategyResponse,
        current_parameters: dict[str, Any],
        recent_history: list[dict[str, Any]],
        optimization_targets: list[OptimizationTarget],
    ) -> dict[str, Any] | None:
        """获取AI优化建议"""
        if not recent_history:
            return None

        history_summary = "\n".join(
            [f"Iteration {h['iteration']}: Score={h['score']:.3f}, Params={h['parameters']}" for h in recent_history]
        )

        prompt = f"""
基于以下优化历史，请建议参数调整方向：

策略: {strategy_response.strategy_name}
当前参数: {current_parameters}
优化目标: {[t.metric.value for t in optimization_targets]}

最近优化历史:
{history_summary}

请分析趋势并建议具体的参数调整值，返回JSON格式：
{{
    "parameter_name": suggested_value,
    ...
}}

如果趋势不明显，请返回null。
"""

        try:
            response = await self.ai_provider.generate_strategy(
                type(
                    "obj",
                    (object,),
                    {
                        "prompt": prompt,
                        "strategy_type": None,
                        "complexity_level": strategy_response.complexity_level,
                        "target_assets": [],
                        "timeframe": "1d",
                        "risk_tolerance": "medium",
                        "max_positions": 10,
                        "backtest_period": "1y",
                        "custom_requirements": [],
                        "context_data": None,
                    },
                )()
            )

            # 尝试解析AI建议
            import json

            suggestions = json.loads(response.reasoning or "{}")

            # 验证建议的参数是否在有效范围内
            valid_suggestions = {}
            for param in strategy_response.parameters:
                if param.name in suggestions and param.range:
                    value = suggestions[param.name]
                    min_val = param.range.get("min")
                    max_val = param.range.get("max")

                    if min_val is not None and value < min_val:
                        value = min_val
                    if max_val is not None and value > max_val:
                        value = max_val

                    valid_suggestions[param.name] = value

            return valid_suggestions if valid_suggestions else None

        except Exception as e:
            self.logger.warning(f"Failed to get AI optimization suggestion: {e}")
            return None
