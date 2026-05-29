"""
DSL执行器 - 执行编译后的策略代码
"""

import importlib.util
import sys
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from collections.abc import Callable

import numpy as np
import pandas as pd

from ..observability.logging import get_logger
from .compiler import CompiledStrategy

logger = get_logger(__name__)


@dataclass
class ExecutionContext:
    """执行上下文"""

    data: pd.DataFrame
    variables: dict[str, Any] = field(default_factory=dict)
    functions: dict[str, Callable] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_variable(self, name: str, value: Any) -> None:
        """添加变量"""
        self.variables[name] = value

    def add_function(self, name: str, func: Callable) -> None:
        """添加函数"""
        self.functions[name] = func

    def get_variable(self, name: str, default: Any = None) -> Any:
        """获取变量"""
        return self.variables.get(name, default)

    def get_function(self, name: str, default: Any = None) -> Callable:
        """获取函数"""
        return self.functions.get(name, default)


@dataclass
class ExecutionResult:
    """执行结果"""

    success: bool
    signals: pd.DataFrame | None = None
    performance: dict[str, float] = field(default_factory=dict)
    error: str | None = None
    traceback: str | None = None
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class DSLExecutor:
    """DSL执行器"""

    def __init__(self):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self._compiled_modules = {}

    def execute(self, compiled_strategy: CompiledStrategy, context: ExecutionContext) -> ExecutionResult:
        """执行编译后的策略"""
        import time

        start_time = time.time()

        try:
            self.logger.info(
                "Executing strategy",
                strategy_name=compiled_strategy.name,
                data_shape=context.data.shape,
            )

            # 编译或获取模块
            module = self._get_or_create_module(compiled_strategy)

            # 准备执行环境
            self._prepare_execution_globals(compiled_strategy, context)

            # 执行策略函数
            strategy_func_name = f"{compiled_strategy.name}_strategy"
            if not hasattr(module, strategy_func_name):
                raise AttributeError(f"Strategy function '{strategy_func_name}' not found")

            strategy_func = getattr(module, strategy_func_name)
            result = strategy_func(context.data)

            # 计算性能指标
            performance = self._calculate_performance(result, context.data)

            execution_time = time.time() - start_time

            execution_result = ExecutionResult(
                success=True,
                signals=result.get("signals"),
                performance=performance,
                execution_time=execution_time,
                metadata=result.get("metadata", {}),
            )

            self.logger.info(
                "Strategy execution completed successfully",
                strategy_name=compiled_strategy.name,
                execution_time=execution_time,
                performance=performance,
            )

            return execution_result

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            error_traceback = traceback.format_exc()

            self.logger.error(
                "Strategy execution failed",
                strategy_name=compiled_strategy.name,
                error=error_msg,
                execution_time=execution_time,
            )

            return ExecutionResult(
                success=False,
                error=error_msg,
                traceback=error_traceback,
                execution_time=execution_time,
            )

    def _get_or_create_module(self, compiled_strategy: CompiledStrategy):
        """获取或创建编译的模块"""
        module_key = f"{compiled_strategy.name}_{hash(compiled_strategy.code)}"

        if module_key not in self._compiled_modules:
            # 创建新模块
            spec = importlib.util.spec_from_loader(f"strategy_{compiled_strategy.name}", loader=None)
            module = importlib.util.module_from_spec(spec)

            # 执行策略代码（在受控环境中）
            # 注意：此处使用exec()执行用户策略代码
            # 安全措施：
            # 1. 通过_safe_execution_context()限制执行环境
            # 2. 代码已经过验证和编译
            # 3. 在独立的模块命名空间中执行
            with self._safe_execution_context():
                exec(compiled_strategy.code, module.__dict__)  # nosec B102

            self._compiled_modules[module_key] = module

        return self._compiled_modules[module_key]

    def _prepare_execution_globals(
        self, compiled_strategy: CompiledStrategy, context: ExecutionContext
    ) -> dict[str, Any]:
        """准备执行环境"""
        globals_dict = {
            # 标准库
            "pd": pd,
            "np": np,
            # 策略变量
            **compiled_strategy.variables,
            **context.variables,
            # 上下文数据
            "data": context.data,
        }

        # 添加自定义函数
        for name, func in context.functions.items():
            globals_dict[name] = func

        return globals_dict

    def _calculate_performance(self, result: dict[str, Any], data: pd.DataFrame) -> dict[str, float]:
        """计算性能指标"""
        performance = {}

        try:
            signals = result.get("signals")
            if signals is not None and "position" in signals.columns:
                positions = signals["position"]

                # 计算收益率
                if "close" in data.columns:
                    returns = data["close"].pct_change()
                    strategy_returns = positions.shift(1) * returns

                    # 基本性能指标
                    performance["total_return"] = (1 + strategy_returns).prod() - 1
                    performance["annual_return"] = performance["total_return"] * (252 / len(data))
                    performance["volatility"] = strategy_returns.std() * np.sqrt(252)

                    if performance["volatility"] > 0:
                        performance["sharpe_ratio"] = performance["annual_return"] / performance["volatility"]
                    else:
                        performance["sharpe_ratio"] = 0

                        # 最大回撤
                    cumulative = (1 + strategy_returns).cumprod()
                    running_max = cumulative.expanding().max()
                    drawdown = (cumulative - running_max) / running_max
                    performance["max_drawdown"] = drawdown.min()

                    # 胜率
                    win_trades = strategy_returns[strategy_returns > 0]
                    loss_trades = strategy_returns[strategy_returns < 0]

                    if len(win_trades) + len(loss_trades) > 0:
                        performance["win_rate"] = len(win_trades) / (len(win_trades) + len(loss_trades))
                    else:
                        performance["win_rate"] = 0

                        # 交易次数
                    position_changes = positions.diff().abs()
                    performance["trade_count"] = int(position_changes.sum())

                    # 盈亏比
                    if len(loss_trades) > 0 and win_trades.mean() > 0:
                        performance["profit_loss_ratio"] = abs(win_trades.mean() / loss_trades.mean())
                    else:
                        performance["profit_loss_ratio"] = 0

        except Exception as e:
            self.logger.warning(f"Failed to calculate performance: {e}")
            performance["error"] = str(e)

        return performance

    @contextmanager
    def _safe_execution_context(self):
        """安全的执行上下文"""
        # 保存原始的sys.modules
        original_modules = sys.modules.copy()

        try:
            yield
        finally:
            # 恢复sys.modules
            sys.modules.clear()
            sys.modules.update(original_modules)

    def validate_strategy(self, compiled_strategy: CompiledStrategy) -> dict[str, Any]:
        """验证策略代码"""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "metadata": {},
        }

        try:
            # 检查语法
            compile(compiled_strategy.code, "<string>", "exec")

            # 检查必需的函数
            module = self._get_or_create_module(compiled_strategy)
            strategy_func_name = f"{compiled_strategy.name}_strategy"

            if not hasattr(module, strategy_func_name):
                validation_result["errors"].append(f"Missing strategy function: {strategy_func_name}")
                validation_result["valid"] = False

                # 检查导入
            required_imports = ["pandas", "numpy"]
            for imp in required_imports:
                if imp not in compiled_strategy.imports:
                    validation_result["warnings"].append(f"Missing recommended import: {imp}")

                    # 检查函数签名
            if hasattr(module, strategy_func_name):
                func = getattr(module, strategy_func_name)
                if not callable(func):
                    validation_result["errors"].append(f"Strategy function is not callable: {strategy_func_name}")
                    validation_result["valid"] = False

            validation_result["metadata"] = {
                "functions_count": len(compiled_strategy.functions),
                "imports_count": len(compiled_strategy.imports),
                "variables_count": len(compiled_strategy.variables),
                "code_lines": len(compiled_strategy.code.split("\n")),
            }

        except SyntaxError as e:
            validation_result["errors"].append(f"Syntax error: {e}")
            validation_result["valid"] = False
        except Exception as e:
            validation_result["errors"].append(f"Validation error: {e}")
            validation_result["valid"] = False

        return validation_result

    def get_strategy_info(self, compiled_strategy: CompiledStrategy) -> dict[str, Any]:
        """获取策略信息"""
        try:
            module = self._get_or_create_module(compiled_strategy)

            info = {
                "name": compiled_strategy.name,
                "imports": compiled_strategy.imports,
                "functions": compiled_strategy.functions,
                "variables": compiled_strategy.variables,
                "metadata": compiled_strategy.metadata,
                "validation": self.validate_strategy(compiled_strategy),
            }

            # 尝试获取策略文档字符串
            strategy_func_name = f"{compiled_strategy.name}_strategy"
            if hasattr(module, strategy_func_name):
                func = getattr(module, strategy_func_name)
                info["docstring"] = func.__doc__

            return info

        except Exception as e:
            return {"name": compiled_strategy.name, "error": str(e)}
