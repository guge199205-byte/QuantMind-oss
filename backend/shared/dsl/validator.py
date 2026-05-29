"""
DSL验证器 - 验证DSL语法和逻辑
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import ValidationError, validate

from ..observability.logging import get_logger
from .parser import StrategyDSL

logger = get_logger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema_v1.json"
_schema_cache = None


def load_schema() -> dict:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _schema_cache


def validate_strategy_dsl(doc: Any) -> tuple[bool, str | None]:
    """使用JSON Schema验证DSL文档"""
    schema = load_schema()
    try:
        validate(instance=doc, schema=schema)
        return True, None
    except ValidationError as e:
        return False, e.message


@dataclass
class ValidationIssue:
    """验证问题"""

    type: str  # error, warning, info
    message: str
    line: int | None = None
    column: int | None = None
    rule: str | None = None
    suggestion: str | None = None


@dataclass
class ValidationResult:
    """验证结果"""

    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    score: float = 0.0  # 0-100
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_error(self, message: str, **kwargs):
        """添加错误"""
        self.issues.append(ValidationIssue(type="error", message=message, **kwargs))
        self.is_valid = False

    def add_warning(self, message: str, **kwargs):
        """添加警告"""
        self.issues.append(ValidationIssue(type="warning", message=message, **kwargs))

    def add_info(self, message: str, **kwargs):
        """添加信息"""
        self.issues.append(ValidationIssue(type="info", message=message, **kwargs))


class DSLValidator:
    """DSL验证器"""

    def __init__(self):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.valid_functions = {
            "ma",
            "ema",
            "sma",
            "wma",
            "rsi",
            "macd",
            "bollinger",
            "cross",
            "above",
            "below",
            "highest",
            "lowest",
            "rank",
            "abs",
            "sqrt",
            "log",
            "exp",
            "sign",
            "round",
            "floor",
            "ceil",
            "returns",
            "log_returns",
            "volatility",
            "drawdown",
        }
        self.valid_indicators = {"price", "close", "open", "high", "low", "volume"}
        self.valid_actions = {"buy", "sell", "hold"}
        self.valid_operators = {
            "+",
            "-",
            "*",
            "/",
            ">",
            "<",
            ">=",
            "<=",
            "==",
            "!=",
            "and",
            "or",
            "not",
        }

    def validate(self, strategy_dsl: StrategyDSL) -> ValidationResult:
        """验证DSL策略"""
        result = ValidationResult(is_valid=True)

        try:
            self.logger.info(
                "Starting DSL validation",
                strategy_name=strategy_dsl.name,
                rules_count=len(strategy_dsl.rules),
            )

            # JSON Schema验证
            schema_valid, schema_error = validate_strategy_dsl(strategy_dsl.to_dict())
            if not schema_valid:
                result.add_error(f"JSON Schema validation failed: {schema_error}")

            # 基本结构验证
            self._validate_basic_structure(strategy_dsl, result)

            # 变量验证
            self._validate_variables(strategy_dsl, result)

            # 规则验证
            self._validate_rules(strategy_dsl, result)

            # 逻辑验证
            self._validate_logic(strategy_dsl, result)

            # 性能验证
            self._validate_performance(strategy_dsl, result)

            # 计算验证分数
            result.score = self._calculate_validation_score(result)

            self.logger.info(
                "DSL validation completed",
                strategy_name=strategy_dsl.name,
                is_valid=result.is_valid,
                score=result.score,
                issues_count=len(result.issues),
            )

            return result

        except Exception as e:
            self.logger.error(f"DSL validation failed: {e}")
            result.add_error(f"Validation error: {e}")
            return result

    def _validate_basic_structure(self, strategy_dsl: StrategyDSL, result: ValidationResult):
        """验证基本结构"""
        # 检查策略名称
        if not strategy_dsl.name or not isinstance(strategy_dsl.name, str):
            result.add_error("Strategy name is required and must be a string")
        elif not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", strategy_dsl.name):
            result.add_error(f"Invalid strategy name: {strategy_dsl.name}. Must be a valid identifier")

        # 检查是否有规则
        if not strategy_dsl.rules:
            result.add_warning("Strategy has no rules defined")

        # 检查元数据
        if not strategy_dsl.metadata:
            result.add_info("No metadata provided")

    def _validate_variables(self, strategy_dsl: StrategyDSL, result: ValidationResult):
        """验证变量"""
        for name, value in strategy_dsl.variables.items():
            # 检查变量名
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
                result.add_error(f"Invalid variable name: {name}")

            # 检查变量值
            if isinstance(value, str):
                if not value.strip():
                    result.add_warning(f"Variable {name} is empty string")
            elif isinstance(value, (int, float)):
                if isinstance(value, float) and (value != value):  # NaN check
                    result.add_error(f"Variable {name} is NaN")
                elif value < 0 and name.endswith(("_period", "_length", "_window")):
                    result.add_error(f"Period variable {name} cannot be negative")
                elif value == 0 and name.endswith(("_period", "_length", "_window")):
                    result.add_error(f"Period variable {name} cannot be zero")
            elif isinstance(value, list):
                if not value:
                    result.add_warning(f"Variable {name} is empty list")

    def _validate_rules(self, strategy_dsl: StrategyDSL, result: ValidationResult):
        """验证规则"""
        for i, rule in enumerate(strategy_dsl.rules):
            rule_prefix = f"Rule {i}"

            # 检查规则类型
            if "type" not in rule:
                result.add_error(f"{rule_prefix}: Missing rule type")
                continue

            rule_type = rule["type"]

            if rule_type == "action":
                self._validate_action_rule(rule, rule_prefix, result)
            elif rule_type == "conditional":
                self._validate_conditional_rule(rule, rule_prefix, result)
            else:
                result.add_error(f"{rule_prefix}: Unknown rule type: {rule_type}")

    def _validate_action_rule(self, rule: dict[str, Any], rule_prefix: str, result: ValidationResult):
        """验证动作规则"""
        action = rule.get("action")
        if not action:
            result.add_error(f"{rule_prefix}: Missing action")
            return

        if action not in self.valid_actions:
            result.add_error(f"{rule_prefix}: Invalid action: {action}")

        # 验证参数
        parameters = rule.get("parameters", {})
        if not isinstance(parameters, dict):
            result.add_error(f"{rule_prefix}: Parameters must be a dictionary")

        # 检查特定动作的参数
        if action in ["buy", "sell"]:
            if "quantity" in parameters:
                quantity = parameters["quantity"]
                if not isinstance(quantity, (int, float)) or quantity <= 0:
                    result.add_error(f"{rule_prefix}: Invalid quantity: {quantity}")

    def _validate_conditional_rule(self, rule: dict[str, Any], rule_prefix: str, result: ValidationResult):
        """验证条件规则"""
        condition = rule.get("condition")
        if not condition:
            result.add_error(f"{rule_prefix}: Missing condition")
            return

        # 验证条件表达式
        self._validate_condition_expression(condition, f"{rule_prefix} condition", result)

        # 验证then动作
        then_action = rule.get("then_action")
        if then_action:
            if isinstance(then_action, dict):
                self._validate_action_rule(then_action, f"{rule_prefix} then", result)
            else:
                result.add_error(f"{rule_prefix}: then_action must be a dictionary")

        # 验证else动作
        else_action = rule.get("else_action")
        if else_action:
            if isinstance(else_action, dict):
                self._validate_action_rule(else_action, f"{rule_prefix} else", result)
            else:
                result.add_error(f"{rule_prefix}: else_action must be a dictionary")

    def _validate_condition_expression(self, condition: Any, context: str, result: ValidationResult):
        """验证条件表达式"""
        if isinstance(condition, str):
            # 检查语法
            try:
                # 简单的语法检查
                if any(op in condition for op in self.valid_operators):
                    # 检查函数调用
                    for func in self.valid_functions:
                        pattern = rf"\b{func}\s*\("
                        if re.search(pattern, condition):
                            # 验证函数参数
                            self._validate_function_call(condition, func, context, result)

                    # 检查指标引用
                    for indicator in self.valid_indicators:
                        if indicator in condition:
                            result.add_info(f"{context}: Using indicator: {indicator}")
                else:
                    result.add_warning(f"{context}: No operators found in condition")

            except Exception as e:
                result.add_error(f"{context}: Invalid condition syntax: {e}")

        elif isinstance(condition, dict):
            # 验证字典形式的条件
            if "operator" in condition:
                operator = condition["operator"]
                if operator not in self.valid_operators:
                    result.add_error(f"{context}: Invalid operator: {operator}")

                left = condition.get("left")
                right = condition.get("right")

                if left is not None:
                    self._validate_condition_expression(left, f"{context} left", result)
                if right is not None:
                    self._validate_condition_expression(right, f"{context} right", result)

            elif "function" in condition:
                func_name = condition["function"]
                if func_name not in self.valid_functions:
                    result.add_error(f"{context}: Unknown function: {func_name}")

                args = condition.get("args", [])
                for i, arg in enumerate(args):
                    self._validate_condition_expression(arg, f"{context} arg {i}", result)

        else:
            result.add_error(f"{context}: Invalid condition type: {type(condition)}")

    def _validate_function_call(self, expression: str, func_name: str, context: str, result: ValidationResult):
        """验证函数调用"""
        try:
            # 提取函数参数
            pattern = rf"{func_name}\s*\(([^)]*)\)"
            match = re.search(pattern, expression)

            if match:
                args_str = match.group(1)
                if args_str.strip():
                    args = [arg.strip() for arg in args_str.split(",")]

                    # 验证特定函数的参数
                    if func_name in ["ma", "ema", "sma", "wma", "rsi"]:
                        if len(args) != 2:
                            result.add_error(f"{context}: {func_name} requires 2 arguments (data, period)")
                        else:
                            try:
                                period = int(args[1])
                                if period <= 0:
                                    result.add_error(f"{context}: {func_name} period must be positive")
                                elif period > 500:
                                    result.add_warning(f"{context}: {func_name} period very large: {period}")
                            except ValueError:
                                result.add_error(f"{context}: {func_name} period must be an integer")

                    elif func_name == "macd":
                        if len(args) < 3:
                            result.add_error(f"{context}: macd requires at least 3 arguments")

                    elif func_name == "bollinger":
                        if len(args) < 2:
                            result.add_error(f"{context}: bollinger requires at least 2 arguments")

        except Exception as e:
            result.add_warning(f"{context}: Failed to validate {func_name} call: {e}")

    def _validate_logic(self, strategy_dsl: StrategyDSL, result: ValidationResult):
        """验证逻辑"""
        # 检查是否有买入和卖出规则
        has_buy = any(rule.get("action") == "buy" for rule in strategy_dsl.rules if rule.get("type") == "action")
        has_sell = any(rule.get("action") == "sell" for rule in strategy_dsl.rules if rule.get("type") == "action")

        if not has_buy:
            result.add_warning("Strategy has no buy rules")
        if not has_sell:
            result.add_warning("Strategy has no sell rules")

        # 检查条件规则中的动作
        for rule in strategy_dsl.rules:
            if rule.get("type") == "conditional":
                then_action = rule.get("then_action", {})
                if then_action.get("action") == "buy":
                    has_buy = True
                elif then_action.get("action") == "sell":
                    has_sell = True

        # 检查循环依赖
        self._check_circular_dependencies(strategy_dsl, result)

    def _check_circular_dependencies(self, strategy_dsl: StrategyDSL, result: ValidationResult):
        """检查循环依赖"""
        # 简单的循环依赖检查
        variable_refs = {}

        # 收集变量引用
        for name, value in strategy_dsl.variables.items():
            if isinstance(value, str):
                # 查找其他变量的引用
                for other_name in strategy_dsl.variables:
                    if other_name != name and other_name in value:
                        if name not in variable_refs:
                            variable_refs[name] = []
                        variable_refs[name].append(other_name)

        # 检查循环
        for var, refs in variable_refs.items():
            for ref in refs:
                if ref in variable_refs and var in variable_refs[ref]:
                    result.add_error(f"Circular dependency detected: {var} <-> {ref}")

    def _validate_performance(self, strategy_dsl: StrategyDSL, result: ValidationResult):
        """验证性能相关"""
        # 检查规则数量
        rule_count = len(strategy_dsl.rules)
        if rule_count > 50:
            result.add_warning(f"Strategy has many rules ({rule_count}), may impact performance")
        elif rule_count < 2:
            result.add_info("Strategy has very few rules, may be too simple")

        # 检查变量数量
        var_count = len(strategy_dsl.variables)
        if var_count > 100:
            result.add_warning(f"Strategy has many variables ({var_count}), may impact performance")

        # 检查复杂度
        complexity_score = self._calculate_complexity(strategy_dsl)
        if complexity_score > 100:
            result.add_warning(f"Strategy complexity is high ({complexity_score})")

        result.metadata["complexity_score"] = complexity_score
        result.metadata["rule_count"] = rule_count
        result.metadata["variable_count"] = var_count

    def _calculate_complexity(self, strategy_dsl: StrategyDSL) -> int:
        """计算复杂度分数"""
        complexity = 0

        # 基础复杂度
        complexity += len(strategy_dsl.rules) * 2
        complexity += len(strategy_dsl.variables)

        # 规则复杂度
        for rule in strategy_dsl.rules:
            if rule.get("type") == "conditional":
                complexity += 3  # 条件规则更复杂
                condition = rule.get("condition", "")
                if isinstance(condition, str):
                    # 计算操作符数量
                    for op in self.valid_operators:
                        complexity += condition.count(op) * 1

        return complexity

    def _calculate_validation_score(self, result: ValidationResult) -> float:
        """计算验证分数 (0-100)"""
        if not result.is_valid:
            return 0.0

        score = 100.0

        # 根据问题扣分
        for issue in result.issues:
            if issue.type == "error":
                score -= 20.0
            elif issue.type == "warning":
                score -= 5.0
            elif issue.type == "info":
                score -= 1.0

        return max(0.0, score)
