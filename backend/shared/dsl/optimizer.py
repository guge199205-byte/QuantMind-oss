"""
DSL优化器 - 优化DSL策略性能
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..observability.logging import get_logger
from .compiler import CompiledStrategy, DSLCompiler
from .executor import DSLExecutor, ExecutionContext, ExecutionResult
from .parser import StrategyDSL

logger = get_logger(__name__)


@dataclass
class OptimizationTarget:
    """优化目标"""

    metric: str  # sharpe_ratio, total_return, max_drawdown, win_rate
    weight: float = 1.0
    target_value: float | None = None
    minimize: bool = False


@dataclass
class OptimizationResult:
    """优化结果"""

    best_dsl: StrategyDSL
    best_compiled: CompiledStrategy
    best_result: ExecutionResult
    optimization_history: list[dict[str, Any]] = field(default_factory=list)
    improvement: dict[str, float] = field(default_factory=dict)
    optimization_time: float = 0.0
    iterations: int = 0


class DSLOptimizer:
    """DSL优化器"""

    def __init__(self):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.compiler = DSLCompiler()
        self.executor = DSLExecutor()

    def optimize(
        self,
        strategy_dsl: StrategyDSL,
        context: ExecutionContext,
        targets: list[OptimizationTarget],
        max_iterations: int = 20,
    ) -> OptimizationResult:
        """优化DSL策略"""
        import time

        start_time = time.time()

        self.logger.info(
            "Starting DSL optimization",
            strategy_name=strategy_dsl.name,
            targets=[t.metric for t in targets],
            max_iterations=max_iterations,
        )

        # 初始编译和执行
        initial_compiled = self.compiler.compile(strategy_dsl)
        initial_result = self.executor.execute(initial_compiled, context)

        best_dsl = strategy_dsl
        best_compiled = initial_compiled
        best_result = initial_result
        best_score = self._calculate_optimization_score(initial_result, targets)

        optimization_history = []

        # 记录初始状态
        optimization_history.append(
            {
                "iteration": 0,
                "score": best_score,
                "performance": initial_result.performance,
                "changes": "Initial state",
            }
        )

        # 优化迭代
        for iteration in range(1, max_iterations + 1):
            self.logger.debug(f"Optimization iteration {iteration}/{max_iterations}")

            # 生成DSL变体
            dsl_variants = self._generate_dsl_variants(best_dsl, iteration)

            # 评估变体
            for i, variant in enumerate(dsl_variants):
                try:
                    # 编译变体
                    compiled_variant = self.compiler.compile(variant)

                    # 执行变体
                    result = self.executor.execute(compiled_variant, context)

                    if result.success:
                        # 计算优化分数
                        score = self._calculate_optimization_score(result, targets)

                        # 记录历史
                        optimization_history.append(
                            {
                                "iteration": iteration,
                                "variant": i,
                                "score": score,
                                "performance": result.performance,
                                "changes": self._describe_changes(best_dsl, variant),
                            }
                        )

                        # 更新最佳结果
                        if self._is_better_score(score, best_score, targets):
                            best_dsl = variant
                            best_compiled = compiled_variant
                            best_result = result
                            best_score = score

                            self.logger.debug(f"Found better strategy at iteration {iteration}, score: {score:.4f}")

                except Exception as e:
                    self.logger.warning(f"Failed to evaluate variant {i} at iteration {iteration}: {e}")
                    continue

            # 自适应调整
            if iteration % 5 == 0:
                self._adaptive_adjustment(optimization_history[-5:], targets)

        optimization_time = time.time() - start_time

        # 计算改进
        improvement = self._calculate_improvement(initial_result, best_result)

        result = OptimizationResult(
            best_dsl=best_dsl,
            best_compiled=best_compiled,
            best_result=best_result,
            optimization_history=optimization_history,
            improvement=improvement,
            optimization_time=optimization_time,
            iterations=max_iterations,
        )

        self.logger.info(
            "DSL optimization completed",
            strategy_name=strategy_dsl.name,
            best_score=best_score,
            improvement=improvement,
            time=optimization_time,
        )

        return result

    def _generate_dsl_variants(self, strategy_dsl: StrategyDSL, iteration: int) -> list[StrategyDSL]:
        """生成DSL变体"""
        variants = []

        # 参数优化
        param_variants = self._optimize_parameters(strategy_dsl, iteration)
        variants.extend(param_variants)

        # 规则优化
        rule_variants = self._optimize_rules(strategy_dsl, iteration)
        variants.extend(rule_variants)

        # 结构优化
        if iteration % 3 == 0:
            structure_variants = self._optimize_structure(strategy_dsl)
            variants.extend(structure_variants)

        return variants

    def _optimize_parameters(self, strategy_dsl: StrategyDSL, iteration: int) -> list[StrategyDSL]:
        """优化参数"""
        variants = []

        # 识别数值参数
        numeric_params = {}
        for name, value in strategy_dsl.variables.items():
            if isinstance(value, (int, float)):
                numeric_params[name] = value

        # 为每个数值参数生成变体
        for param_name, param_value in numeric_params.items():
            # 生成3个变体：-10%, 0%, +10%
            for adjustment in [-0.1, 0.0, 0.1]:
                new_value = param_value * (1 + adjustment)

                # 确保参数在合理范围内
                if param_name.startswith("period") or param_name.endswith("_period"):
                    new_value = max(1, min(200, int(new_value)))
                elif param_name.endswith("_threshold") or param_name.endswith("_level"):
                    new_value = max(0.01, min(1.0, new_value))

                new_variables = strategy_dsl.variables.copy()
                new_variables[param_name] = new_value

                variant = StrategyDSL(
                    name=f"{strategy_dsl.name}_param_{param_name}_{iteration}",
                    variables=new_variables,
                    rules=strategy_dsl.rules.copy(),
                    metadata={
                        **strategy_dsl.metadata,
                        "optimization": f"param_{param_name}",
                    },
                )
                variants.append(variant)

        return variants

    def _optimize_rules(self, strategy_dsl: StrategyDSL, iteration: int) -> list[StrategyDSL]:
        """优化规则"""
        variants = []

        for i, rule in enumerate(strategy_dsl.rules):
            # 修改规则条件
            if rule["type"] == "conditional":
                variant_rule = self._modify_conditional_rule(rule)
                if variant_rule:
                    new_rules = strategy_dsl.rules.copy()
                    new_rules[i] = variant_rule

                    variant = StrategyDSL(
                        name=f"{strategy_dsl.name}_rule_{i}_{iteration}",
                        variables=strategy_dsl.variables.copy(),
                        rules=new_rules,
                        metadata={**strategy_dsl.metadata, "optimization": f"rule_{i}"},
                    )
                    variants.append(variant)

            # 修改动作参数
            elif rule["type"] == "action":
                variant_rule = self._modify_action_rule(rule)
                if variant_rule:
                    new_rules = strategy_dsl.rules.copy()
                    new_rules[i] = variant_rule

                    variant = StrategyDSL(
                        name=f"{strategy_dsl.name}_action_{i}_{iteration}",
                        variables=strategy_dsl.variables.copy(),
                        rules=new_rules,
                        metadata={
                            **strategy_dsl.metadata,
                            "optimization": f"action_{i}",
                        },
                    )
                    variants.append(variant)

        return variants

    def _optimize_structure(self, strategy_dsl: StrategyDSL) -> list[StrategyDSL]:
        """优化结构"""
        variants = []

        # 添加风险控制规则
        risk_rule = {
            "type": "conditional",
            "condition": "drawdown(close) > 0.1",
            "then_action": {"type": "action", "action": "sell", "parameters": {}},
            "else_action": None,
        }

        new_rules = strategy_dsl.rules + [risk_rule]
        variant = StrategyDSL(
            name=f"{strategy_dsl.name}_risk_control",
            variables=strategy_dsl.variables.copy(),
            rules=new_rules,
            metadata={**strategy_dsl.metadata, "optimization": "risk_control"},
        )
        variants.append(variant)

        # 添加止损规则
        stop_loss_rule = {
            "type": "conditional",
            "condition": "returns(close) < -0.05",
            "then_action": {"type": "action", "action": "sell", "parameters": {}},
            "else_action": None,
        }

        new_rules = strategy_dsl.rules + [stop_loss_rule]
        variant = StrategyDSL(
            name=f"{strategy_dsl.name}_stop_loss",
            variables=strategy_dsl.variables.copy(),
            rules=new_rules,
            metadata={**strategy_dsl.metadata, "optimization": "stop_loss"},
        )
        variants.append(variant)

        return variants

    def _modify_conditional_rule(self, rule: dict[str, Any]) -> dict[str, Any] | None:
        """修改条件规则"""
        try:
            new_rule = rule.copy()

            # 修改条件阈值
            condition = rule.get("condition", "")
            if ">" in condition:
                # 增加阈值
                parts = condition.split(">")
                if len(parts) == 2:
                    try:
                        threshold = float(parts[1].strip())
                        new_threshold = threshold * 1.1  # 增加10%
                        new_rule["condition"] = f"{parts[0].strip()} > {new_threshold}"
                    except ValueError:
                        pass
            elif "<" in condition:
                # 减少阈值
                parts = condition.split("<")
                if len(parts) == 2:
                    try:
                        threshold = float(parts[1].strip())
                        new_threshold = threshold * 0.9  # 减少10%
                        new_rule["condition"] = f"{parts[0].strip()} < {new_threshold}"
                    except ValueError:
                        pass

            return new_rule

        except Exception:
            return None

    def _modify_action_rule(self, rule: dict[str, Any]) -> dict[str, Any] | None:
        """修改动作规则"""
        try:
            new_rule = rule.copy()

            # 修改动作参数
            parameters = rule.get("parameters", {})

            # 添加延迟执行
            if "delay" not in parameters:
                parameters["delay"] = 1
                new_rule["parameters"] = parameters

            return new_rule

        except Exception:
            return None

    def _calculate_optimization_score(self, result: ExecutionResult, targets: list[OptimizationTarget]) -> float:
        """计算优化分数"""
        if not result.success:
            return float("-in")

        total_score = 0.0
        total_weight = 0.0

        for target in targets:
            metric_value = result.performance.get(target.metric, 0.0)
            weight = target.weight

            if target.minimize:
                # 对于要最小化的指标（如最大回撤）
                if metric_value < 0:
                    score = weight / abs(metric_value) if metric_value != 0 else weight
                else:
                    score = weight / (1.0 + metric_value)
            else:
                # 对于要最大化的指标
                score = weight * metric_value

            total_score += score
            total_weight += weight

        return total_score / total_weight if total_weight > 0 else 0.0

    def _is_better_score(self, new_score: float, current_score: float, targets: list[OptimizationTarget]) -> bool:
        """判断是否是更好的分数"""
        if targets and targets[0].minimize:
            return new_score < current_score
        else:
            return new_score > current_score

    def _describe_changes(self, original: StrategyDSL, modified: StrategyDSL) -> str:
        """描述变化"""
        changes = []

        # 检查变量变化
        for name in set(original.variables.keys()) | set(modified.variables.keys()):
            orig_val = original.variables.get(name)
            mod_val = modified.variables.get(name)
            if orig_val != mod_val:
                changes.append(f"{name}: {orig_val} -> {mod_val}")

        # 检查规则变化
        if len(original.rules) != len(modified.rules):
            changes.append(f"rules count: {len(original.rules)} -> {len(modified.rules)}")

        return "; ".join(changes) if changes else "structural changes"

    def _adaptive_adjustment(self, recent_history: list[dict[str, Any]], targets: list[OptimizationTarget]) -> None:
        """自适应调整"""
        if len(recent_history) < 3:
            return

        # 分析最近的改进趋势
        scores = [h["score"] for h in recent_history]

        # 如果分数没有显著改进，调整策略
        if max(scores) - min(scores) < 0.01:
            self.logger.info("Applying adaptive adjustment due to slow convergence")
            # 这里可以实现更复杂的自适应逻辑

    def _calculate_improvement(self, initial: ExecutionResult, best: ExecutionResult) -> dict[str, float]:
        """计算改进"""
        improvement = {}

        if initial.success and best.success:
            for metric in initial.performance:
                initial_val = initial.performance.get(metric, 0.0)
                best_val = best.performance.get(metric, 0.0)

                if initial_val != 0:
                    improvement[metric] = (best_val - initial_val) / abs(initial_val)
                else:
                    improvement[metric] = best_val

        return improvement
