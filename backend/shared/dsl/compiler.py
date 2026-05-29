"""
DSL编译器 - 将DSL编译为可执行的Python代码
"""

import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..observability.logging import get_logger
from .parser import StrategyDSL

logger = get_logger(__name__)


@dataclass
class CompiledStrategy:
    """编译后的策略"""

    name: str
    code: str
    imports: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "code": self.code,
            "imports": self.imports,
            "functions": self.functions,
            "variables": self.variables,
            "metadata": self.metadata,
        }


class DSLCompiler:
    """DSL编译器"""

    def __init__(self):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.built_in_functions = {
            "ma",
            "ema",
            "rsi",
            "macd",
            "bollinger",
            "sma",
            "wma",
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
        }
        self.built_in_indicators = {
            "price",
            "close",
            "open",
            "high",
            "low",
            "volume",
            "returns",
            "log_returns",
            "volatility",
            "drawdown",
        }

    def compile(self, strategy_dsl: StrategyDSL) -> CompiledStrategy:
        """编译DSL为Python代码"""
        try:
            self.logger.info(
                "Starting DSL compilation",
                strategy_name=strategy_dsl.name,
                rules_count=len(strategy_dsl.rules),
            )

            # 生成导入语句
            imports = self._generate_imports()

            # 生成变量定义
            variables_code = self._generate_variables(strategy_dsl.variables)

            # 生成辅助函数
            functions_code = self._generate_functions()

            # 生成策略主函数
            strategy_code = self._generate_strategy_function(strategy_dsl)

            # 组合完整代码
            full_code = self._combine_code(imports, variables_code, functions_code, strategy_code)

            # 验证生成的代码
            self._validate_code(full_code)

            compiled_strategy = CompiledStrategy(
                name=strategy_dsl.name,
                code=full_code,
                imports=imports,
                functions=self._extract_function_names(full_code),
                variables=strategy_dsl.variables,
                metadata=strategy_dsl.metadata,
            )

            self.logger.info(
                "DSL compilation completed successfully",
                strategy_name=strategy_dsl.name,
                code_lines=len(full_code.split("\n")),
            )

            return compiled_strategy

        except Exception as e:
            self.logger.error(f"DSL compilation failed: {e}")
            raise

    def _generate_imports(self) -> list[str]:
        """生成导入语句"""
        return [
            "import numpy as np",
            "import pandas as pd",
            "from typing import Dict, List, Any, Optional",
            "from dataclasses import dataclass",
            "import warnings",
            "warnings.filterwarnings('ignore')",
        ]

    def _generate_variables(self, variables: dict[str, Any]) -> str:
        """生成变量定义代码"""
        if not variables:
            return ""

        lines = []
        lines.append("# Strategy Variables")
        for name, value in variables.items():
            if isinstance(value, str):
                lines.append(f"{name} = '{value}'")
            else:
                lines.append(f"{name} = {value}")

        return "\n".join(lines)

    def _generate_functions(self) -> str:
        """生成辅助函数"""
        functions = []

        # 技术指标函数
        functions.append(self._generate_technical_indicators())

        # 交易辅助函数
        functions.append(self._generate_trading_helpers())

        # 条件判断函数
        functions.append(self._generate_condition_helpers())

        return "\n\n".join(functions)

    def _generate_technical_indicators(self) -> str:
        """生成技术指标函数"""
        return '''
# Technical Indicators
def ma(data: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average"""
    return data.rolling(window=period).mean()

def ema(data: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average"""
    return data.ewm(span=period).mean()

def sma(data: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average (alias)"""
    return ma(data, period)

def wma(data: pd.Series, period: int) -> pd.Series:
    """Weighted Moving Average"""
    weights = np.arange(1, period + 1)
    return data.rolling(window=period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
    """MACD Indicator"""
    ema_fast = ema(data, fast)
    ema_slow = ema(data, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line

    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }

def bollinger(data: pd.Series, period: int = 20, std_dev: float = 2) -> Dict[str, pd.Series]:
    """Bollinger Bands"""
    sma_line = sma(data, period)
    std_line = data.rolling(window=period).std()
    upper_band = sma_line + (std_line * std_dev)
    lower_band = sma_line - (std_dev * std_dev)

    return {
        'upper': upper_band,
        'middle': sma_line,
        'lower': lower_band
    }

def highest(data: pd.Series, period: int) -> pd.Series:
    """Highest value over period"""
    return data.rolling(window=period).max()

def lowest(data: pd.Series, period: int) -> pd.Series:
    """Lowest value over period"""
    return data.rolling(window=period).min()

def rank(data: pd.Series, ascending: bool = False) -> pd.Series:
    """Rank values"""
    return data.rank(ascending=ascending)
'''

    def _generate_trading_helpers(self) -> str:
        """生成交易辅助函数"""
        return '''
# Trading Helper Functions
def cross(series1: pd.Series, series2: pd.Series) -> pd.Series:
    """Check if series1 crosses series2"""
    return (series1 > series2) & (series1.shift(1) <= series2.shift(1))

def above(series1: pd.Series, series2: pd.Series) -> pd.Series:
    """Check if series1 is above series2"""
    return series1 > series2

def below(series1: pd.Series, series2: pd.Series) -> pd.Series:
    """Check if series1 is below series2"""
    return series1 < series2

def returns(data: pd.Series, periods: int = 1) -> pd.Series:
    """Calculate returns"""
    return data.pct_change(periods)

def log_returns(data: pd.Series, periods: int = 1) -> pd.Series:
    """Calculate log returns"""
    return np.log(data / data.shift(periods))

def volatility(data: pd.Series, period: int = 20) -> pd.Series:
    """Calculate rolling volatility"""
    return returns(data).rolling(window=period).std() * np.sqrt(252)

def drawdown(data: pd.Series) -> pd.Series:
    """Calculate drawdown"""
    cumulative = (1 + returns(data)).cumprod()
    running_max = cumulative.expanding().max()
    return (cumulative - running_max) / running_max
'''

    def _generate_condition_helpers(self) -> str:
        """生成条件判断辅助函数"""
        return '''
# Condition Helper Functions
def abs_value(data: pd.Series) -> pd.Series:
    """Absolute value"""
    return abs(data)

def sqrt_value(data: pd.Series) -> pd.Series:
    """Square root"""
    return np.sqrt(data)

def log_value(data: pd.Series) -> pd.Series:
    """Natural logarithm"""
    return np.log(data)

def exp_value(data: pd.Series) -> pd.Series:
    """Exponential"""
    return np.exp(data)

def sign(data: pd.Series) -> pd.Series:
    """Sign function"""
    return np.sign(data)

def round_value(data: pd.Series, decimals: int = 0) -> pd.Series:
    """Round values"""
    return data.round(decimals)

def floor_value(data: pd.Series) -> pd.Series:
    """Floor values"""
    return np.floor(data)

def ceil_value(data: pd.Series) -> pd.Series:
    """Ceiling values"""
    return np.ceil(data)
'''

    def _generate_strategy_function(self, strategy_dsl: StrategyDSL) -> str:
        """生成策略主函数"""
        function_lines = []

        # 函数定义
        function_lines.append(f"def {strategy_dsl.name}_strategy(data: pd.DataFrame) -> Dict[str, Any]:")
        function_lines.append('    """')
        function_lines.append(f"    Generated strategy: {strategy_dsl.name}")
        function_lines.append('    """')
        function_lines.append("")

        # 初始化
        function_lines.append("    # Initialize results")
        function_lines.append("    signals = pd.DataFrame(index=data.index)")
        function_lines.append('    signals["position"] = 0')
        function_lines.append("")

        # 提取价格数据
        function_lines.append("    # Extract price data")
        function_lines.append('    close = data["close"] if "close" in data.columns else data.iloc[:, 0]')
        function_lines.append('    open_price = data["open"] if "open" in data.columns else close')
        function_lines.append('    high = data["high"] if "high" in data.columns else close')
        function_lines.append('    low = data["low"] if "low" in data.columns else close')
        function_lines.append(
            '    volume = data["volume"] if "volume" in data.columns else pd.Series(1, index=data.index)'
        )
        function_lines.append("")

        # 生成规则代码
        for i, rule in enumerate(strategy_dsl.rules):
            rule_code = self._generate_rule_code(rule, i)
            function_lines.extend(f"    {line}" for line in rule_code.split("\n"))
            function_lines.append("")

        # 返回结果
        function_lines.append("    # Return strategy results")
        function_lines.append("    return {")
        function_lines.append('        "signals": signals,')
        function_lines.append(f'        "strategy_name": "{strategy_dsl.name}",')
        function_lines.append(f'        "metadata": {strategy_dsl.metadata}')
        function_lines.append("    }")

        return "\n".join(function_lines)

    def _generate_rule_code(self, rule: dict[str, Any], rule_index: int) -> str:
        """生成规则代码"""
        if rule["type"] == "action":
            return self._generate_action_code(rule, rule_index)
        elif rule["type"] == "conditional":
            return self._generate_conditional_code(rule, rule_index)
        else:
            return f"# Unknown rule type: {rule['type']}"

    def _generate_action_code(self, rule: dict[str, Any], rule_index: int) -> str:
        """生成动作代码"""
        action = rule["action"]
        rule.get("parameters", {})

        if action == "buy":
            return f'signals.loc[signals.index[{rule_index}:], "position"] = 1  # Buy signal'
        elif action == "sell":
            return f'signals.loc[signals.index[{rule_index}:], "position"] = -1  # Sell signal'
        elif action == "hold":
            return f"# Hold position at index {rule_index}"
        else:
            return f"# Unknown action: {action}"

    def _generate_conditional_code(self, rule: dict[str, Any], rule_index: int) -> str:
        """生成条件代码"""
        condition = rule["condition"]
        then_action = rule["then_action"]
        else_action = rule.get("else_action")

        # 生成条件表达式
        condition_code = self._generate_condition_expression(condition)

        # 生成动作代码
        then_code = self._generate_action_code(then_action, rule_index)

        if else_action:
            else_code = self._generate_action_code(else_action, rule_index)
            return f"""if {condition_code}:
    {then_code}
else:
    {else_code}"""
        else:
            return f"""if {condition_code}:
    {then_code}"""

    def _generate_condition_expression(self, condition: Any) -> str:
        """生成条件表达式"""
        if isinstance(condition, str):
            return condition
        elif isinstance(condition, dict):
            if "operator" in condition:
                left = self._generate_condition_expression(condition["left"])
                right = self._generate_condition_expression(condition["right"])
                op = condition["operator"]
                return f"{left} {op} {right}"
            elif "function" in condition:
                func_name = condition["function"]
                args = [self._generate_condition_expression(arg) for arg in condition.get("args", [])]
                return f"{func_name}({', '.join(args)})"

        return str(condition)

    def _combine_code(self, imports: list[str], variables: str, functions: str, strategy: str) -> str:
        """组合完整代码"""
        parts = []

        # 添加文件头注释
        parts.append("# Generated Strategy Code")
        parts.append("# Do not edit manually - regenerate from DSL")
        parts.append("")

        # 添加导入
        if imports:
            parts.append("# Imports")
            parts.extend(imports)
            parts.append("")

        # 添加变量
        if variables:
            parts.append("# Variables")
            parts.append(variables)
            parts.append("")

        # 添加函数
        if functions:
            parts.append("# Helper Functions")
            parts.append(functions)
            parts.append("")

        # 添加策略函数
        parts.append("# Strategy Function")
        parts.append(strategy)

        return "\n".join(parts)

    def _validate_code(self, code: str) -> None:
        """验证生成的Python代码"""
        try:
            # 尝试解析AST
            ast.parse(code)
        except SyntaxError as e:
            raise SyntaxError(f"Generated code has syntax error: {e}")

    def _extract_function_names(self, code: str) -> list[str]:
        """提取代码中的函数名"""
        try:
            tree = ast.parse(code)
            functions = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)

            return functions
        except Exception:
            return []
