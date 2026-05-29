"""
策略-回测闭环管理器
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..ai_providers import AIProviderFactory, StrategyRequest, StrategyResponse
from ..backtest_engine import BacktestConfig, BacktestEngine, BacktestResult
from ..dsl import DSLCompiler, DSLExecutor, DSLParser, DSLValidator, ExecutionContext
from ..observability.logging import get_logger

logger = get_logger(__name__)


class LoopStage(Enum):
    """闭环阶段"""

    STRATEGY_GENERATION = "strategy_generation"
    DSL_COMPILATION = "dsl_compilation"
    BACKTEST_EXECUTION = "backtest_execution"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    STRATEGY_OPTIMIZATION = "strategy_optimization"
    FEEDBACK_LEARNING = "feedback_learning"


@dataclass
class LoopConfig:
    """闭环配置"""

    max_iterations: int = 10
    target_metrics: dict[str, float] = field(
        default_factory=lambda: {
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.15,
            "win_rate": 0.6,
            "annual_return": 0.2,
        }
    )
    optimization_threshold: float = 0.05  # 5%改进阈值
    ai_provider: str = "deepseek"
    backtest_period: str = "2y"
    data_frequency: str = "1d"
    risk_tolerance: str = "medium"


@dataclass
class LoopIteration:
    """单次迭代结果"""

    iteration: int
    stage: LoopStage
    strategy_request: StrategyRequest
    strategy_response: StrategyResponse | None = None
    dsl_compiled: bool = False
    backtest_result: BacktestResult | None = None
    performance_score: float = 0.0
    improvement: float = 0.0
    feedback: dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    errors: list[str] = field(default_factory=list)


@dataclass
class LoopResult:
    """闭环结果"""

    success: bool
    total_iterations: int
    best_iteration: LoopIteration
    all_iterations: list[LoopIteration] = field(default_factory=list)
    final_strategy: StrategyResponse | None = None
    learning_insights: dict[str, Any] = field(default_factory=dict)
    total_time: float = 0.0


class StrategyBacktestLoop:
    """策略-回测闭环管理器"""

    def __init__(self, config: LoopConfig):
        self.config = config
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

        # 初始化组件
        self.ai_provider = AIProviderFactory.get_provider(config.ai_provider)
        self.dsl_parser = DSLParser()
        self.dsl_compiler = DSLCompiler()
        self.dsl_executor = DSLExecutor()
        self.dsl_validator = DSLValidator()
        self.backtest_engine = BacktestEngine()

        # 状态跟踪
        self.current_iteration = 0
        self.best_score = float("-in")
        self.best_iteration = None

    async def run_loop(self, initial_request: StrategyRequest, market_data: dict[str, Any]) -> LoopResult:
        """运行策略-回测闭环"""
        start_time = time.time()

        self.logger.info(
            "Starting strategy-backtest loop",
            strategy_name=initial_request.prompt[:50],
            max_iterations=self.config.max_iterations,
            target_metrics=self.config.target_metrics,
        )

        iterations = []
        current_request = initial_request

        try:
            # 初始化AI Provider
            await self.ai_provider.initialize()

            # 主循环
            for iteration in range(1, self.config.max_iterations + 1):
                self.current_iteration = iteration

                loop_iteration = await self._run_single_iteration(iteration, current_request, market_data)

                iterations.append(loop_iteration)

                # 检查是否达到目标
                if self._check_targets_met(loop_iteration):
                    self.logger.info(f"Targets met at iteration {iteration}")
                    break

                # 检查是否有显著改进
                if loop_iteration.performance_score > self.best_score:
                    self.best_score = loop_iteration.performance_score
                    self.best_iteration = loop_iteration
                    current_request = self._generate_next_request(loop_iteration)
                else:
                    # 如果没有改进，调整策略
                    current_request = self._adjust_request(current_request, loop_iteration)

                # 检查是否应该提前终止
                if iteration > 3 and self._should_terminate_early(iterations):
                    self.logger.info(f"Early termination at iteration {iteration}")
                    break

            # 构建最终结果
            total_time = time.time() - start_time
            best_iter = self.best_iteration or iterations[-1]

            result = LoopResult(
                success=True,
                total_iterations=len(iterations),
                best_iteration=best_iter,
                all_iterations=iterations,
                final_strategy=best_iter.strategy_response,
                learning_insights=self._generate_learning_insights(iterations),
                total_time=total_time,
            )

            self.logger.info(
                "Strategy-backtest loop completed successfully",
                total_iterations=len(iterations),
                best_score=self.best_score,
                total_time=total_time,
            )

            return result

        except Exception as e:
            self.logger.error(f"Strategy-backtest loop failed: {e}")

            return LoopResult(
                success=False,
                total_iterations=len(iterations),
                best_iteration=iterations[-1] if iterations else None,
                all_iterations=iterations,
                total_time=time.time() - start_time,
            )

    async def _run_single_iteration(
        self, iteration: int, request: StrategyRequest, market_data: dict[str, Any]
    ) -> LoopIteration:
        """运行单次迭代"""
        start_time = time.time()

        loop_iteration = LoopIteration(
            iteration=iteration,
            stage=LoopStage.STRATEGY_GENERATION,
            strategy_request=request,
        )

        try:
            # 阶段1: 策略生成
            self.logger.debug(f"Iteration {iteration}: Generating strategy")
            strategy_response = await self.ai_provider.generate_strategy(request)
            loop_iteration.strategy_response = strategy_response

            if not strategy_response:
                loop_iteration.errors.append("Failed to generate strategy")
                return loop_iteration

            # 阶段2: DSL编译
            loop_iteration.stage = LoopStage.DSL_COMPILATION
            self.logger.debug(f"Iteration {iteration}: Compiling DSL")

            # 将策略代码转换为DSL
            dsl_text = self._convert_to_dsl(strategy_response)
            strategy_dsl = self.dsl_parser.parse(dsl_text)

            # 验证DSL
            validation_result = self.dsl_validator.validate(strategy_dsl)
            if not validation_result.is_valid:
                loop_iteration.errors.extend(
                    [issue.message for issue in validation_result.issues if issue.type == "error"]
                )
                return loop_iteration

            # 编译DSL
            compiled_strategy = self.dsl_compiler.compile(strategy_dsl)
            loop_iteration.dsl_compiled = True

            # 阶段3: 回测执行
            loop_iteration.stage = LoopStage.BACKTEST_EXECUTION
            self.logger.debug(f"Iteration {iteration}: Running backtest")

            # 创建执行上下文
            execution_context = ExecutionContext(data=market_data["data"], variables=strategy_dsl.variables)

            # 执行策略
            execution_result = self.dsl_executor.execute(compiled_strategy, execution_context)

            if not execution_result.success:
                loop_iteration.errors.append(f"Strategy execution failed: {execution_result.error}")
                return loop_iteration

            # 阶段4: 性能分析
            loop_iteration.stage = LoopStage.PERFORMANCE_ANALYSIS
            self.logger.debug(f"Iteration {iteration}: Analyzing performance")

            # 运行回测
            backtest_config = BacktestConfig(
                start_date=market_data["start_date"],
                end_date=market_data["end_date"],
                initial_capital=100000,
                commission=0.001,
            )

            backtest_result = self.backtest_engine.run_backtest(
                execution_result.signals, market_data["data"], backtest_config
            )

            loop_iteration.backtest_result = backtest_result

            # 计算性能分数
            performance_score = self._calculate_performance_score(backtest_result)
            loop_iteration.performance_score = performance_score

            # 计算改进
            if self.best_score > 0:
                loop_iteration.improvement = (performance_score - self.best_score) / self.best_score

            # 阶段5: 生成反馈
            loop_iteration.stage = LoopStage.FEEDBACK_LEARNING
            loop_iteration.feedback = self._generate_feedback(loop_iteration, market_data)

            loop_iteration.execution_time = time.time() - start_time

            self.logger.debug(
                f"Iteration {iteration} completed",
                performance_score=performance_score,
                improvement=loop_iteration.improvement,
                time=loop_iteration.execution_time,
            )

            return loop_iteration

        except Exception as e:
            loop_iteration.errors.append(str(e))
            loop_iteration.execution_time = time.time() - start_time

            self.logger.error(f"Iteration {iteration} failed: {e}")
            return loop_iteration

    def _convert_to_dsl(self, strategy_response: StrategyResponse) -> str:
        """将策略响应转换为DSL"""
        # 这里是一个简化的实现，实际中需要更复杂的转换逻辑
        dsl_lines = []

        dsl_lines.append(f"strategy {strategy_response.strategy_name}")
        dsl_lines.append("{")

        # 添加变量定义
        for param in strategy_response.parameters:
            if param.range and "default_value" in param.__dict__:
                dsl_lines.append(f"    define {param.name} = {param.default_value}")

        # 添加规则（简化版）
        dsl_lines.append("    if (ma(close, 20) > close) then")
        dsl_lines.append("        buy()")
        dsl_lines.append("    else")
        dsl_lines.append("        sell()")

        dsl_lines.append("}")

        return "\n".join(dsl_lines)

    def _calculate_performance_score(self, backtest_result: BacktestResult) -> float:
        """计算综合性能分数"""
        if not backtest_result or not backtest_result.performance_metrics:
            return 0.0

        metrics = backtest_result.performance_metrics

        # 基于目标指标计算分数
        score = 0.0

        # Sharpe比率 (权重: 30%)
        sharpe = metrics.get("sharpe_ratio", 0)
        target_sharpe = self.config.target_metrics.get("sharpe_ratio", 1.5)
        score += min(sharpe / target_sharpe, 2.0) * 0.3

        # 最大回撤 (权重: 25%)
        max_dd = abs(metrics.get("max_drawdown", 0))
        target_dd = abs(self.config.target_metrics.get("max_drawdown", -0.15))
        score += min(target_dd / max_dd if max_dd > 0 else 2.0, 2.0) * 0.25

        # 胜率 (权重: 20%)
        win_rate = metrics.get("win_rate", 0)
        target_win_rate = self.config.target_metrics.get("win_rate", 0.6)
        score += min(win_rate / target_win_rate, 2.0) * 0.2

        # 年化收益率 (权重: 25%)
        annual_return = metrics.get("annual_return", 0)
        target_return = self.config.target_metrics.get("annual_return", 0.2)
        score += min(annual_return / target_return, 2.0) * 0.25

        return score

    def _check_targets_met(self, iteration: LoopIteration) -> bool:
        """检查是否达到目标指标"""
        if not iteration.backtest_result or not iteration.backtest_result.performance_metrics:
            return False

        metrics = iteration.backtest_result.performance_metrics

        for metric, target in self.config.target_metrics.items():
            value = metrics.get(metric, 0)

            if metric in ["sharpe_ratio", "win_rate", "annual_return"]:
                if value < target:
                    return False
            elif metric in ["max_drawdown"]:
                if value > target:  # 回撤是负数，所以是大于
                    return False

        return True

    def _generate_next_request(self, iteration: LoopIteration) -> StrategyRequest:
        """生成下一次迭代的请求"""
        base_request = iteration.strategy_request

        # 基于反馈调整请求
        feedback = iteration.feedback

        # 添加优化建议到请求中
        new_requirements = base_request.custom_requirements.copy()

        if feedback.get("suggestions"):
            new_requirements.extend(feedback["suggestions"])

        if feedback.get("parameter_adjustments"):
            for param, adjustment in feedback["parameter_adjustments"].items():
                new_requirements.append(f"Adjust {param} to {adjustment}")

        return StrategyRequest(
            prompt=base_request.prompt,
            strategy_type=base_request.strategy_type,
            complexity_level=base_request.complexity_level,
            target_assets=base_request.target_assets,
            timeframe=base_request.timeframe,
            risk_tolerance=base_request.risk_tolerance,
            max_positions=base_request.max_positions,
            backtest_period=base_request.backtest_period,
            custom_requirements=new_requirements,
            context_data={
                **(base_request.context_data or {}),
                "previous_performance": (
                    iteration.backtest_result.performance_metrics if iteration.backtest_result else {}
                ),
                "iteration": iteration.iteration,
                "feedback": feedback,
            },
        )

    def _adjust_request(self, request: StrategyRequest, iteration: LoopIteration) -> StrategyRequest:
        """调整请求以改进策略"""
        # 如果性能不佳，调整复杂度或风险偏好
        new_request = StrategyRequest(
            prompt=request.prompt,
            strategy_type=request.strategy_type,
            complexity_level=request.complexity_level,
            target_assets=request.target_assets,
            timeframe=request.timeframe,
            risk_tolerance=request.risk_tolerance,
            max_positions=request.max_positions,
            backtest_period=request.backtest_period,
            custom_requirements=request.custom_requirements.copy(),
            context_data=request.context_data,
        )

        # 如果胜率低，降低风险
        if iteration.backtest_result and iteration.backtest_result.performance_metrics.get("win_rate", 0) < 0.4:
            new_request.risk_tolerance = "low"
            new_request.custom_requirements.append("Focus on higher probability trades with stricter entry conditions")

        # 如果收益率低，增加激进程度
        elif iteration.backtest_result and iteration.backtest_result.performance_metrics.get("annual_return", 0) < 0.1:
            new_request.risk_tolerance = "high"
            new_request.custom_requirements.append(
                "Increase position sizing and consider more aggressive entry signals"
            )

        return new_request

    def _should_terminate_early(self, iterations: list[LoopIteration]) -> bool:
        """判断是否应该提前终止"""
        if len(iterations) < 3:
            return False

        # 检查最近几次迭代是否有改进
        recent_scores = [iter.performance_score for iter in iterations[-3:]]
        improvements = [recent_scores[i] - recent_scores[i - 1] for i in range(1, len(recent_scores))]

        # 如果连续3次改进都小于阈值，终止
        return all(imp < self.config.optimization_threshold for imp in improvements)

    def _generate_feedback(self, iteration: LoopIteration, market_data: dict[str, Any]) -> dict[str, Any]:
        """生成反馈"""
        feedback = {
            "suggestions": [],
            "parameter_adjustments": {},
            "performance_issues": [],
            "strengths": [],
        }

        if not iteration.backtest_result:
            return feedback

        metrics = iteration.backtest_result.performance_metrics

        # 分析性能问题
        if metrics.get("sharpe_ratio", 0) < 1.0:
            feedback["performance_issues"].append("Low risk-adjusted returns")
            feedback["suggestions"].append("Improve risk management and position sizing")

        if abs(metrics.get("max_drawdown", 0)) > 0.2:
            feedback["performance_issues"].append("High maximum drawdown")
            feedback["suggestions"].append("Add stop-loss mechanisms and reduce position sizes")

        if metrics.get("win_rate", 0) < 0.5:
            feedback["performance_issues"].append("Low win rate")
            feedback["suggestions"].append("Refine entry conditions and add confirmation signals")

        # 分析优势
        if metrics.get("sharpe_ratio", 0) > 1.5:
            feedback["strengths"].append("Good risk-adjusted returns")

        if metrics.get("win_rate", 0) > 0.6:
            feedback["strengths"].append("High win rate")

        return feedback

    def _generate_learning_insights(self, iterations: list[LoopIteration]) -> dict[str, Any]:
        """生成学习洞察"""
        insights = {
            "total_iterations": len(iterations),
            "best_performance": (max(iter.performance_score for iter in iterations) if iterations else 0),
            "improvement_trend": [],
            "common_issues": [],
            "successful_patterns": [],
        }

        # 分析改进趋势
        scores = [iter.performance_score for iter in iterations]
        for i in range(1, len(scores)):
            improvement = scores[i] - scores[i - 1]
            insights["improvement_trend"].append(improvement)

        # 分析常见问题
        all_errors = []
        for iter in iterations:
            all_errors.extend(iter.errors)

        # 统计错误频率
        error_counts = {}
        for error in all_errors:
            error_counts[error] = error_counts.get(error, 0) + 1

        insights["common_issues"] = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return insights
