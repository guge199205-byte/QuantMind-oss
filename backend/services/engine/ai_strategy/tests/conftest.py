"""
Pytest配置文件和共享fixtures
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.fixture
def mock_deepseek_api():
    """Mock DeepSeek API响应"""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "strategy_name": "测试策略",
                                "rationale": "这是一个基于MACD指标的测试策略",
                                "python_code": "def initialize(context):\n    pass\n\ndef handle_data(context, data):\n    pass",
                                "factors": ["MACD", "RSI"],
                                "risk_controls": ["止损5%", "止盈20%"],
                                "assumptions": ["市场正常交易"],
                                "notes": "测试备注",
                            }
                        )
                    }
                }
            ],
            "model": "deepseek-chat",
        }
        mock_post.return_value = mock_response
        yield mock_post


@pytest.fixture
def mock_deepseek_error():
    """Mock DeepSeek API错误"""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        yield mock_post


@pytest.fixture
def sample_strategy_params():
    """示例策略参数"""
    return {
        "description": "MACD金叉买入策略",
        "market": "CN",
        "risk_level": "medium",
        "style": "simple",
        "user_id": "test_user",
    }


@pytest.fixture
def valid_qlib_code():
    """有效的Qlib策略代码"""
    return """
import pandas as pd
import numpy as np
from qlib.contrib.strategy.base import BaseStrategy

STRATEGY_CONFIG = {
    "universe": "csi300",
    "start_time": "2023-01-01",
    "end_time": "2024-01-01",
    "account": 100000
}

class MomentumStrategy(BaseStrategy):
    def generate_trade_decision(self, execute_result=None):
        return []
"""


@pytest.fixture
def invalid_qlib_code_syntax():
    """语法错误的代码"""
    return """
import pandas
def test(:
    pass
"""


@pytest.fixture
def invalid_qlib_code_dangerous():
    """包含危险导入的代码"""
    return """
import os
import subprocess

os.system("ls")

STRATEGY_CONFIG = {}
"""


@pytest.fixture
def mock_database():
    """Mock数据库连接"""
    with patch("sqlalchemy.create_engine") as mock_engine:
        mock_conn = Mock()
        mock_engine.return_value.connect.return_value = mock_conn
        yield mock_engine
