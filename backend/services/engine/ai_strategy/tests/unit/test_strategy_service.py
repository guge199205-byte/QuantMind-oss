"""
策略生成服务单元测试（对齐当前实现）
"""

import json
import sys
from pathlib import Path

import pytest

from backend.services.engine.ai_strategy.services.strategy_service import (
    StrategyService,
)

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))


class TestStrategyService:
    def test_init_with_valid_api_key(self):
        service = StrategyService(api_key="sk-test123")
        assert service.api_key == "sk-test123"
        assert service.api_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def test_init_with_custom_url(self):
        service = StrategyService(
            api_key="sk-test123",
            api_url="https://custom.api.com",
        )
        assert service.api_url == "https://custom.api.com"

    def test_is_available_with_valid_key(self):
        service = StrategyService(api_key="sk-test123")
        assert service.is_available() is True

    def test_is_available_with_short_key(self):
        service = StrategyService(api_key="abc")
        assert service.is_available() is False

    def test_is_available_with_empty_key(self):
        service = StrategyService(api_key="")
        assert not service.is_available()

    @pytest.mark.asyncio
    async def test_generate_strategy_empty_description(self):
        service = StrategyService(api_key="sk-test123")
        with pytest.raises(ValueError, match="描述不能为空"):
            await service.generate_strategy(description="")

    @pytest.mark.asyncio
    async def test_generate_strategy_api_unavailable(self):
        service = StrategyService(api_key="abc")
        with pytest.raises(RuntimeError, match="未配置可用的 API Key"):
            await service.generate_strategy(
                description="测试策略",
                market="CN",
                risk_level="medium",
            )

    @pytest.mark.asyncio
    async def test_generate_strategy_success(self, monkeypatch):
        service = StrategyService(api_key="sk-test123")

        async def _mock_call_ai_api(prompt: str, user_id: str) -> str:
            return json.dumps(
                {
                    "strategy_name": "测试策略",
                    "rationale": "策略说明",
                    "python_code": "def initialize(context):\n    pass\n\ndef handle_data(context, data):\n    pass",
                    "factors": ["MA5", "MA20"],
                    "risk_controls": ["止损5%"],
                    "assumptions": ["市场正常"],
                    "notes": "备注",
                }
            )

        monkeypatch.setattr(service, "_call_ai_api", _mock_call_ai_api)

        result = await service.generate_strategy(
            description="MACD金叉买入策略",
            market="CN",
            risk_level="medium",
            style="simple",
            user_id="test_user",
        )

        assert result["strategy_name"] == "测试策略"
        assert "artifacts" in result
        assert result["provider"] == "qwen-max"

    @pytest.mark.asyncio
    async def test_generate_strategy_api_error(self, monkeypatch):
        service = StrategyService(api_key="sk-test123")

        async def _mock_call_ai_api(prompt: str, user_id: str) -> str:
            raise Exception("mock error")

        monkeypatch.setattr(service, "_call_ai_api", _mock_call_ai_api)

        with pytest.raises(RuntimeError, match="策略生成失败"):
            await service.generate_strategy(
                description="测试策略",
                market="CN",
                risk_level="medium",
            )

    def test_build_strategy_prompt(self):
        service = StrategyService(api_key="sk-test123")
        prompt = service._build_strategy_prompt(
            description="MACD策略",
            market="CN",
            risk_level="high",
        )
        assert "MACD策略" in prompt
        assert "CN" in prompt
        assert "high" in prompt
        assert "JSON格式" in prompt
        assert "python_code" in prompt

    def test_parse_strategy_response_invalid_json(self):
        service = StrategyService(api_key="sk-test123")
        result = service._parse_strategy_response(
            content="这不是有效JSON",
            description="测试策略",
            user_id="test_user",
        )
        assert result is not None
        assert "strategy_name" in result
        assert "artifacts" in result

    @pytest.mark.asyncio
    async def test_close(self):
        service = StrategyService(api_key="sk-test123")
        await service.close()
