"""
Qlib验证服务单元测试（对齐当前实现）
"""

import sys
from pathlib import Path

import pytest

from backend.services.engine.ai_strategy.services.qlib_validator import QlibValidator

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))


class TestQlibValidator:
    def test_init(self):
        validator = QlibValidator()
        assert validator is not None

    def test_check_syntax_valid_code(self, valid_qlib_code):
        validator = QlibValidator()
        result = validator._check_syntax(valid_qlib_code)
        assert result.passed is True
        assert result.type == "syntax"

    def test_check_syntax_invalid_code(self, invalid_qlib_code_syntax):
        validator = QlibValidator()
        result = validator._check_syntax(invalid_qlib_code_syntax)
        assert result.passed is False
        assert result.type == "syntax"

    def test_check_imports_safe(self, valid_qlib_code):
        validator = QlibValidator()
        result = validator._check_imports(valid_qlib_code)
        assert result.passed is True
        assert result.type == "import"

    def test_check_imports_dangerous(self, invalid_qlib_code_dangerous):
        validator = QlibValidator()
        result = validator._check_imports(invalid_qlib_code_dangerous)
        assert result.passed is False
        assert result.type == "import"

    def test_check_config_exists(self, valid_qlib_code):
        validator = QlibValidator()
        result = validator._check_config(valid_qlib_code)
        assert result.passed is True
        assert result.type == "config"

    def test_check_config_missing(self):
        validator = QlibValidator()
        code = """
import pandas as pd
from qlib.contrib.strategy.base import BaseStrategy

class TestStrategy(BaseStrategy):
    pass
"""
        result = validator._check_config(code)
        assert result.passed is False
        assert result.type == "config"

    def test_check_strategy_class_exists(self, valid_qlib_code):
        validator = QlibValidator()
        result = validator._check_strategy_class(valid_qlib_code)
        assert result.passed is True
        assert result.type == "strategy"

    @pytest.mark.asyncio
    async def test_validate_code_full_valid(self, valid_qlib_code):
        validator = QlibValidator()
        result = await validator.validate_code(
            code=valid_qlib_code,
            context={"universe_size": 300},
            mode="full",
        )
        assert result.valid is True
        assert len(result.checks) >= 4

    @pytest.mark.asyncio
    async def test_validate_code_syntax_only(self, valid_qlib_code):
        validator = QlibValidator()
        result = await validator.validate_code(
            code=valid_qlib_code,
            context={},
            mode="syntax_only",
        )
        assert result.valid is True
        assert len(result.checks) == 1
        assert result.checks[0].type == "syntax"
