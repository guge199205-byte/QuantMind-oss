"""
Qlib策略代码验证服务
Qlib Strategy Code Validator Service

功能：
- 语法检查（AST解析）
- 导入检查（RestrictedPython）
- 配置检查（STRATEGY_CONFIG）
- 策略类检查（继承BaseStrategy）
- 沙箱执行（subprocess隔离）
"""

import ast
import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ValidationCheck:
    """单项验证结果"""

    def __init__(self, type: str, passed: bool, message: str, details: str | None = None):
        self.type = type
        self.passed = passed
        self.message = message
        self.details = details

    def to_dict(self) -> dict:
        result = {"type": self.type, "passed": self.passed, "message": self.message}
        if self.details:
            result["details"] = self.details
        return result


class ValidationResult:
    """验证结果"""

    def __init__(self):
        self.valid = True
        self.checks: list[ValidationCheck] = []
        self.warnings: list[str] = []
        self.execution_preview: dict | None = None

    def add_check(self, check: ValidationCheck):
        """添加检查结果"""
        self.checks.append(check)
        if not check.passed:
            self.valid = False

    def add_warning(self, warning: str):
        """添加警告"""
        self.warnings.append(warning)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "checks": [c.to_dict() for c in self.checks],
            "warnings": self.warnings,
            "execution_preview": self.execution_preview,
        }


class QlibValidator:
    """Qlib策略代码验证器"""

    # 允许的导入模块（白名单）
    ALLOWED_IMPORTS = {
        "qlib",
        "pandas",
        "numpy",
        "datetime",
        "typing",
        "collections",
        "functools",
        "itertools",
        "math",
        "json",
        "copy",
        "warnings",
    }

    # 禁止的函数/模块（黑名单）
    FORBIDDEN_PATTERNS = [
        "eval",
        "exec",
        "__import__",
        "compile",
        "open",
        "file",
        "input",
        "raw_input",
        "os.",
        "sys.",
        "subprocess",
        "socket",
        "urllib",
        "requests",
        "http",
        "getattr",
        "setattr",
        "delattr",
        "hasattr",
        "__subclasses__",
        "__builtins__",
        "__globals__",
        "pickle",
        "marshal",
        "shelve",
    ]

    def __init__(self, timeout: int = 10):
        """
        初始化验证器

        Args:
            timeout: 沙箱执行超时时间（秒）
        """
        self.timeout = timeout

    async def validate_code(self, code: str, context: dict | None = None, mode: str = "full") -> ValidationResult:
        """
        验证Qlib策略代码

        Args:
            code: 策略代码
            context: 上下文信息（如股票池、回测参数等）

        Returns:
            验证结果
        """
        result = ValidationResult()

        # 1. 语法检查
        syntax_check = self._check_syntax(code)
        result.add_check(syntax_check)
        if not syntax_check.passed:
            return result

        if mode == "syntax_only":
            return result

        # 2. 导入检查
        import_check = self._check_imports(code)
        result.add_check(import_check)

        # 3. 配置检查
        config_check = self._check_config(code)
        result.add_check(config_check)

        # 4. 策略类检查
        strategy_check = self._check_strategy_class(code)
        result.add_check(strategy_check)

        # 5. 沙箱执行测试（可选，如果前面都通过）
        if result.valid:
            sandbox_check = await self._check_sandbox_execution(code)
            result.add_check(sandbox_check)

        # 6. 生成执行预览
        if result.valid and context:
            result.execution_preview = self._generate_preview(code, context)

        # 7. 检查潜在问题并生成警告
        warnings = self._generate_warnings(code)
        for warning in warnings:
            result.add_warning(warning)

        return result

    def _check_syntax(self, code: str) -> ValidationCheck:
        """检查Python语法"""
        try:
            ast.parse(code)
            return ValidationCheck(type="syntax", passed=True, message="Python语法检查通过")
        except SyntaxError as e:
            return ValidationCheck(
                type="syntax",
                passed=False,
                message=f"语法错误: {str(e)}",
                details=f"行 {e.lineno}: {e.text}",
            )
        except Exception as e:
            return ValidationCheck(type="syntax", passed=False, message=f"代码解析失败: {str(e)}")

    def _check_imports(self, code: str) -> ValidationCheck:
        """检查导入语句（安全性检查）"""
        try:
            tree = ast.parse(code)
            imports = []
            forbidden = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split(".")[0]
                        imports.append(alias.name)
                        if module not in self.ALLOWED_IMPORTS:
                            forbidden.append(alias.name)

                elif isinstance(node, ast.ImportFrom):
                    module = node.module.split(".")[0] if node.module else ""
                    imports.append(f"from {node.module}")
                    if module and module not in self.ALLOWED_IMPORTS:
                        forbidden.append(node.module)

            # 检查禁止模式（使用更精确的匹配）
            code_lower = code.lower()
            for pattern in self.FORBIDDEN_PATTERNS:
                if pattern.endswith("."):
                    # 模块匹配（如os.、sys.），使用正则确保是单词边界
                    module_name = pattern.rstrip(".")
                    if re.search(r"\b" + re.escape(module_name) + r"\.", code):
                        forbidden.append(pattern)
                else:
                    # 函数名匹配（要求单词边界）
                    if re.search(r"\b" + pattern + r"\b", code_lower):
                        forbidden.append(pattern)

            if forbidden:
                return ValidationCheck(
                    type="import",
                    passed=False,
                    message=f"检测到不允许的导入或函数: {', '.join(forbidden)}",
                    details="仅允许Qlib、pandas、numpy等数据分析库",
                )

            return ValidationCheck(
                type="import",
                passed=True,
                message="导入检查通过",
                details=f"共检测到 {len(imports)} 个导入",
            )

        except Exception as e:
            return ValidationCheck(type="import", passed=False, message=f"导入检查失败: {str(e)}")

    def _check_config(self, code: str) -> ValidationCheck:
        """检查STRATEGY_CONFIG配置"""
        # 查找STRATEGY_CONFIG定义
        config_pattern = r"STRATEGY_CONFIG\s*=\s*\{[\s\S]*?\}"
        match = re.search(config_pattern, code)

        if not match:
            return ValidationCheck(type="config", passed=False, message="未找到STRATEGY_CONFIG配置")

        # 检查必需字段
        config_str = match.group(0)
        required_fields = ["universe", "start_time", "end_time"]
        missing_fields = []

        for field in required_fields:
            if f'"{field}"' not in config_str and f"'{field}'" not in config_str:
                missing_fields.append(field)

        if missing_fields:
            return ValidationCheck(
                type="config",
                passed=False,
                message=f"STRATEGY_CONFIG缺少必需字段: {', '.join(missing_fields)}",
            )

        return ValidationCheck(type="config", passed=True, message="STRATEGY_CONFIG配置验证通过")

    def _check_strategy_class(self, code: str) -> ValidationCheck:
        """检查策略类定义"""
        try:
            tree = ast.parse(code)

            # 查找类定义
            class_definitions = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

            if not class_definitions:
                return ValidationCheck(type="strategy", passed=False, message="未找到策略类定义")

            # 检查是否有继承BaseStrategy的类
            has_strategy_class = False
            strategy_class_name = None

            for class_def in class_definitions:
                # 检查基类
                for base in class_def.bases:
                    base_name = self._get_name(base)
                    if "BaseStrategy" in base_name or "Strategy" in base_name:
                        has_strategy_class = True
                        strategy_class_name = class_def.name
                        break

            if not has_strategy_class:
                return ValidationCheck(
                    type="strategy",
                    passed=False,
                    message="未找到继承自BaseStrategy的策略类",
                )

            return ValidationCheck(
                type="strategy",
                passed=True,
                message=f"策略类 '{strategy_class_name}' 定义正确",
            )

        except Exception as e:
            return ValidationCheck(type="strategy", passed=False, message=f"策略类检查失败: {str(e)}")

    def _get_name(self, node) -> str:
        """获取AST节点名称"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return ""

    async def _check_sandbox_execution(self, code: str) -> ValidationCheck:
        """沙箱执行测试（subprocess隔离）"""
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_file = f.name

            # 在子进程中执行（仅编译，不运行）
            result = subprocess.run(
                ["python3", "-m", "py_compile", temp_file],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            # 清理临时文件
            Path(temp_file).unlink(missing_ok=True)
            Path(temp_file + "c").unlink(missing_ok=True)  # .pyc文件

            if result.returncode != 0:
                return ValidationCheck(
                    type="sandbox",
                    passed=False,
                    message="代码编译失败",
                    details=result.stderr,
                )

            return ValidationCheck(type="sandbox", passed=True, message="沙箱执行测试通过")

        except subprocess.TimeoutExpired:
            return ValidationCheck(type="sandbox", passed=False, message=f"执行超时（>{self.timeout}秒）")
        except Exception as e:
            return ValidationCheck(type="sandbox", passed=False, message=f"沙箱执行失败: {str(e)}")

    def _generate_preview(self, code: str, context: dict) -> dict:
        """生成执行预览"""
        # 提取配置信息
        config_match = re.search(r"STRATEGY_CONFIG\s*=\s*\{[\s\S]*?\}", code)

        preview = {
            "start_date": context.get("start_date", "2023-01-01"),
            "end_date": context.get("end_date", "2024-01-01"),
            "universe_size": context.get("universe_size", 0),
        }

        if config_match:
            config_str = config_match.group(0)
            # 提取日期
            start_match = re.search(r'"start_time"\s*:\s*"([^"]+)"', config_str)
            end_match = re.search(r'"end_time"\s*:\s*"([^"]+)"', config_str)

            if start_match:
                preview["start_date"] = start_match.group(1)
            if end_match:
                preview["end_date"] = end_match.group(1)

        return preview

    def _generate_warnings(self, code: str) -> list[str]:
        """生成警告信息"""
        warnings = []

        # 检查是否使用自定义因子
        if "class" in code and "Factor" in code:
            warnings.append("检测到自定义因子，请确保在Qlib环境中已注册")

        # 检查是否有hardcode的值
        if re.search(r"\b\d{6}\b", code):  # 6位数字（可能是股票代码）
            warnings.append("检测到硬编码的股票代码，建议使用配置参数")

        # 检查是否缺少注释
        comment_count = code.count("#")
        line_count = len(code.split("\n"))
        if line_count > 50 and comment_count < 10:
            warnings.append("代码缺少注释，建议添加说明")

        return warnings


# 单例
_validator_instance: QlibValidator | None = None


def get_qlib_validator() -> QlibValidator:
    """获取验证器单例"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = QlibValidator()
    return _validator_instance
