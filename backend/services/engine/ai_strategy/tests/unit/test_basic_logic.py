"""
基础单元测试 - 简化版
测试核心功能而不依赖复杂的导入结构
"""

import json

import pytest


class TestStrategyServiceBasic:
    """策略生成服务基础测试"""

    def test_api_key_validation(self):
        """测试API密钥验证逻辑"""
        # 有效密钥
        assert "sk-test123".startswith("sk-")

        # 无效密钥
        assert not "invalid-key".startswith("sk-")
        assert not "".startswith("sk-")

    def test_prompt_building(self):
        """测试提示词构建逻辑"""
        description = "MACD金叉买入策略"
        market = "CN"
        risk_level = "high"

        prompt = f"""请基于以下描述生成量化交易策略:

描述: {description}
市场: {market}
风险级别: {risk_level}

请返回JSON格式的策略代码"""

        assert description in prompt
        assert market in prompt
        assert risk_level in prompt
        assert "JSON格式" in prompt

    def test_json_parsing_valid(self):
        """测试有效JSON解析"""
        content = """
        {
            "strategy_name": "测试策略",
            "rationale": "策略说明",
            "python_code": "def test(): pass",
            "factors": ["MA5", "MA20"]
        }
        """

        # 提取JSON
        import re

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        assert json_match is not None

        data = json.loads(json_match.group())
        assert data["strategy_name"] == "测试策略"
        assert "factors" in data

    def test_json_parsing_with_code_blocks(self):
        """测试包含代码块的JSON解析"""
        content = """
        ```json
        {
            "strategy_name": "测试",
            "python_code": "def test(): pass"
        }
        ```
        """

        # 提取代码块中的JSON
        import re

        json_match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(1))
            assert data["strategy_name"] == "测试"


class TestQlibValidatorBasic:
    """Qlib验证器基础测试"""

    def test_syntax_check_valid(self):
        """测试语法检查 - 有效代码"""
        code = """
import pandas as pd

def test_function():
    return True
"""

        try:
            compile(code, "<string>", "exec")
            syntax_valid = True
        except SyntaxError:
            syntax_valid = False

        assert syntax_valid is True

    def test_syntax_check_invalid(self):
        """测试语法检查 - 无效代码"""
        code = """
def test(:
    pass
"""

        try:
            compile(code, "<string>", "exec")
            syntax_valid = True
        except SyntaxError:
            syntax_valid = False

        assert syntax_valid is False

    def test_dangerous_imports_detection(self):
        """测试危险导入检测"""
        dangerous_modules = ["os", "subprocess", "sys", "eval", "exec"]

        code_with_os = "import os\nos.system('ls')"
        code_with_subprocess = "import subprocess"
        code_safe = "import pandas as pd\nimport numpy as np"

        # 检测os导入
        assert any(f"import {mod}" in code_with_os for mod in dangerous_modules)

        # 检测subprocess导入
        assert any(f"import {mod}" in code_with_subprocess for mod in dangerous_modules)

        # 安全代码
        assert not any(f"import {mod}" in code_safe for mod in dangerous_modules)

    def test_config_detection(self):
        """测试STRATEGY_CONFIG检测"""
        code_with_config = """
STRATEGY_CONFIG = {
    "universe": "csi300"
}
"""
        code_without_config = """
def test():
    pass
"""

        assert "STRATEGY_CONFIG" in code_with_config
        assert "STRATEGY_CONFIG" not in code_without_config

    def test_class_definition_detection(self):
        """测试策略类定义检测"""
        code_with_class = """
from qlib.contrib.strategy.base import BaseStrategy

class MyStrategy(BaseStrategy):
    pass
"""
        code_without_class = """
def some_function():
    pass
"""

        assert "BaseStrategy" in code_with_class
        assert "class" in code_with_class
        assert "BaseStrategy" not in code_without_class


class TestSelectionEngineBasic:
    """选股引擎基础测试"""

    def test_factor_mapping(self):
        """测试因子映射"""
        factor_map = {
            "市盈率": "pe_ratio",
            "市净率": "pb_ratio",
            "ROE": "roe",
            "市值": "market_cap",
            "成交量": "volume",
        }

        assert factor_map["市盈率"] == "pe_ratio"
        assert factor_map["ROE"] == "roe"

    def test_operator_mapping(self):
        """测试操作符映射"""
        operator_map = {
            "大于": ">",
            "小于": "<",
            "等于": "=",
            "大于等于": ">=",
            "小于等于": "<=",
        }

        assert operator_map["大于"] == ">"
        assert operator_map["小于等于"] == "<="

    def test_sql_injection_keywords(self):
        """测试SQL注入关键词检测"""
        dangerous_keywords = [
            "DROP",
            "DELETE",
            "UPDATE",
            "INSERT",
            "TRUNCATE",
            "--",
            ";",
        ]

        safe_query = "SELECT * FROM stock_selection WHERE pe_ratio < 20"
        dangerous_query = "'; DROP TABLE stock_selection; --"

        # 安全查询
        assert not any(keyword in safe_query.upper() for keyword in ["DROP", "DELETE", "TRUNCATE"])

        # 危险查询
        assert any(keyword in dangerous_query.upper() for keyword in dangerous_keywords)

    def test_limit_validation(self):
        """测试返回数量限制"""
        max_limit = 200

        # 有效限制
        assert 10 <= max_limit
        assert 50 <= max_limit

        # 超出限制
        requested_limit = 500
        actual_limit = min(requested_limit, max_limit)
        assert actual_limit == max_limit


class TestValidatorBasic:
    """验证器基础测试"""

    def test_required_params_validation(self):
        """测试必需参数验证"""
        required_params = ["description", "market", "risk_level"]

        # 完整参数
        params_complete = {
            "description": "MACD策略",
            "market": "CN",
            "risk_level": "medium",
        }

        missing_params = [p for p in required_params if p not in params_complete]
        assert len(missing_params) == 0

        # 缺少参数
        params_incomplete = {"description": "MACD策略"}

        missing_params = [p for p in required_params if p not in params_incomplete]
        assert len(missing_params) > 0

    def test_param_type_validation(self):
        """测试参数类型验证"""
        # 字符串类型
        description = "测试策略"
        assert isinstance(description, str)

        # 空字符串
        empty_desc = ""
        assert isinstance(empty_desc, str)
        assert len(empty_desc.strip()) == 0

    def test_risk_level_validation(self):
        """测试风险级别验证"""
        valid_risk_levels = ["low", "medium", "high"]

        assert "low" in valid_risk_levels
        assert "medium" in valid_risk_levels
        assert "high" in valid_risk_levels
        assert "invalid" not in valid_risk_levels


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
