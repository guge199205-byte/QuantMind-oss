"""
Claude Provider实现
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic

from ..observability.logging import get_logger
from .base import (
    BaseAIProvider,
    ModelConfig,
    ModelType,
    StrategyCode,
    StrategyParameter,
    StrategyRequest,
    StrategyResponse,
)

logger = get_logger(__name__)


class ClaudeProvider(BaseAIProvider):
    """Claude Provider"""

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.client: AsyncAnthropic | None = None
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    async def initialize(self) -> bool:
        """初始化Claude客户端"""
        try:
            self.client = AsyncAnthropic(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
                timeout=self.config.timeout,
                max_retries=self.config.retry_attempts,
            )

            # 测试连接
            await self._test_connection()
            self._is_initialized = True

            self.logger.info("Claude provider initialized successfully", model=self.config.model_name)
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize Claude provider: {e}")
            return False

    async def _test_connection(self):
        """测试连接"""
        try:
            await self.client.messages.create(
                model=self.config.model_name,
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}],
            )
            return True
        except Exception as e:
            raise Exception(f"Claude connection test failed: {e}")

    async def generate_strategy(self, request: StrategyRequest) -> StrategyResponse:
        """生成交易策略"""
        if not self._is_initialized:
            raise RuntimeError("Claude provider not initialized")

        start_time = asyncio.get_event_loop().time()

        try:
            system_prompt = self._build_system_prompt(request)
            user_prompt = f"""
请为以下需求生成量化交易策略：

{request.prompt}

请按照以下JSON格式返回结果：
{{
    "strategy_name": "策略名称",
    "description": "策略详细描述",
    "strategy_type": "momentum|mean_reversion|arbitrage|trend_following|breakout|custom",
    "complexity_level": "basic|intermediate|advanced|expert",
    "code": {{
        "language": "python",
        "code": "完整的Python策略代码",
        "dependencies": ["pandas", "numpy", "其他依赖"],
        "entry_point": "main",
        "description": "代码说明"
    }},
    "parameters": [
        {{
            "name": "参数名",
            "type": "int|float|str|bool",
            "default_value": "默认值",
            "range": {{"min": 最小值, "max": 最大值, "step": 步长}},
            "description": "参数描述",
            "optimization_hints": ["优化提示"]
        }}
    ],
    "risk_indicators": {{
        "max_drawdown": "最大回撤预期",
        "volatility": "波动率预期",
        "risk_level": "low|medium|high"
    }},
    "expected_performance": {{
        "annual_return": 0.15,
        "sharpe_ratio": 1.2,
        "win_rate": 0.6
    }},
    "reasoning": "策略设计思路和理由",
    "confidence_score": 0.85
}}

Claude特别擅长：
- 详细的代码分析和优化
- 风险管理和合规性检查
- 复杂逻辑的清晰表达
- 多因子策略设计
"""

            response = await self.client.messages.create(
                model=self.config.model_name,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                **self.config.custom_params,
            )

            content = response.content[0].text

            # Claude不提供token使用统计，需要估算
            estimated_tokens = self.estimate_tokens(system_prompt + user_prompt + content)
            token_usage = {
                "prompt_tokens": estimated_tokens // 2,
                "completion_tokens": estimated_tokens // 2,
                "total_tokens": estimated_tokens,
            }

            # 解析响应
            strategy_response = self._parse_claude_response(content, request)
            strategy_response.generation_time = asyncio.get_event_loop().time() - start_time
            strategy_response.model_used = self.config.model_name
            strategy_response.token_usage = token_usage

            self.logger.info(
                "Strategy generated successfully",
                strategy=strategy_response.strategy_name,
                tokens=token_usage.get("total_tokens", 0),
                time=strategy_response.generation_time,
            )

            return strategy_response

        except Exception as e:
            self.logger.error(f"Failed to generate strategy: {e}")
            raise

    async def optimize_strategy(
        self,
        strategy_code: str,
        performance_data: dict[str, Any],
        optimization_goals: list[str],
    ) -> StrategyResponse:
        """优化现有策略"""
        if not self._is_initialized:
            raise RuntimeError("Claude provider not initialized")

        try:
            prompt = f"""
请优化以下量化交易策略代码：

当前策略代码：
```python
{strategy_code}
```

性能数据：
{json.dumps(performance_data, indent=2)}

优化目标：
{chr(10).join(f"- {goal}" for goal in optimization_goals)}

Claude的优势在于：
- 深度代码分析和重构
- 风险管理机制优化
- 算法效率提升
- 代码可维护性改进

请提供优化后的策略，按照相同的JSON格式返回。
"""

            response = await self.client.messages.create(
                model=self.config.model_name,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system="你是一个专业的量化交易策略优化专家，擅长深度代码分析和性能优化。",
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text

            # 创建一个基本的请求对象用于解析
            dummy_request = StrategyRequest(
                prompt="Strategy optimization",
                complexity_level=(self.config.complexity_level if hasattr(self.config, "complexity_level") else None),
            )

            optimized_response = self._parse_claude_response(content, dummy_request)
            optimized_response.model_used = self.config.model_name

            return optimized_response

        except Exception as e:
            self.logger.error(f"Failed to optimize strategy: {e}")
            raise

    async def analyze_strategy(self, strategy_code: str) -> dict[str, Any]:
        """分析策略代码"""
        if not self._is_initialized:
            raise RuntimeError("Claude provider not initialized")

        try:
            prompt = f"""
请深入分析以下量化交易策略代码：

```python
{strategy_code}
```

Claude的分析优势：
- 代码结构和架构分析
- 潜在bug和安全漏洞识别
- 性能瓶颈定位
- 最佳实践建议
- 代码质量评估

请提供详细分析，包括：
1. 策略逻辑概述
2. 代码质量评估（1-10分）
3. 潜在风险点
4. 性能瓶颈
5. 改进建议
6. 重构建议

请以JSON格式返回分析结果。
"""

            response = await self.client.messages.create(
                model=self.config.model_name,
                max_tokens=self.config.max_tokens,
                temperature=0.3,
                system="你是一个资深的量化交易策略分析师和代码审查专家。",
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text

            try:
                analysis = json.loads(content)
            except json.JSONDecodeError:
                analysis = {"raw_analysis": content}

            return analysis

        except Exception as e:
            self.logger.error(f"Failed to analyze strategy: {e}")
            raise

    async def validate_strategy(self, strategy_code: str) -> dict[str, Any]:
        """验证策略代码"""
        if not self._is_initialized:
            raise RuntimeError("Claude provider not initialized")

        try:
            prompt = f"""
请严格验证以下量化交易策略代码：

```python
{strategy_code}
```

Claude特别擅长：
- 逻辑一致性检查
- 边界条件分析
- 异常处理验证
- 数据流分析
- 安全性评估

请检查：
1. 语法和逻辑错误
2. 数据处理正确性
3. 风险控制完整性
4. 异常处理机制
5. 性能和安全性

请以JSON格式返回验证结果。
"""

            response = await self.client.messages.create(
                model=self.config.model_name,
                max_tokens=self.config.max_tokens,
                temperature=0.1,
                system="你是一个严谨的代码验证专家，专门负责量化交易策略的全面审查。",
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text

            try:
                validation = json.loads(content)
            except json.JSONDecodeError:
                validation = {
                    "is_valid": False,
                    "error": "Failed to parse validation response",
                    "raw_response": content,
                }

            return validation

        except Exception as e:
            self.logger.error(f"Failed to validate strategy: {e}")
            raise

    def get_supported_models(self) -> list[ModelType]:
        """获取支持的模型列表"""
        return [
            ModelType.CLAUDE_3_SONNET,
            ModelType.CLAUDE_3_OPUS,
            ModelType.CLAUDE_3_HAIKU,
            ModelType.CUSTOM,
        ]

    def estimate_tokens(self, text: str) -> int:
        """估算token数量"""
        # Claude的token估算：大约4个字符 = 1个token
        return len(text) // 4

    def _parse_claude_response(self, content: str, request: StrategyRequest) -> StrategyResponse:
        """解析Claude响应"""
        try:
            # 尝试提取JSON部分
            json_start = content.find("{")
            json_end = content.rfind("}") + 1

            if json_start != -1 and json_end > json_start:
                json_str = content[json_start:json_end]
                data = json.loads(json_str)
            else:
                # 如果无法找到JSON，创建基本响应
                data = {
                    "strategy_name": "Claude Generated Strategy",
                    "description": content,
                    "strategy_type": "custom",
                    "complexity_level": request.complexity_level.value,
                    "code": {
                        "language": "python",
                        "code": content,
                        "dependencies": ["pandas", "numpy"],
                    },
                    "parameters": [],
                    "risk_indicators": {},
                    "expected_performance": {},
                    "reasoning": content,
                    "confidence_score": 0.8,
                }

            # 解析策略类型
            strategy_type = self._parse_strategy_type(data.get("strategy_type", "custom"))
            complexity = self._parse_complexity_level(data.get("complexity_level", "intermediate"))

            # 解析代码
            code_data = data.get("code", {})
            strategy_code = StrategyCode(
                language=code_data.get("language", "python"),
                code=code_data.get("code", ""),
                dependencies=code_data.get("dependencies", []),
                entry_point=code_data.get("entry_point", "main"),
                description=code_data.get("description"),
            )

            # 解析参数
            parameters = []
            for param_data in data.get("parameters", []):
                param = StrategyParameter(
                    name=param_data.get("name", ""),
                    type=param_data.get("type", "float"),
                    default_value=param_data.get("default_value"),
                    range=param_data.get("range"),
                    description=param_data.get("description"),
                    optimization_hints=param_data.get("optimization_hints"),
                )
                parameters.append(param)

            return StrategyResponse(
                strategy_name=data.get("strategy_name", "Claude Generated Strategy"),
                description=data.get("description", ""),
                strategy_type=strategy_type,
                complexity_level=complexity,
                code=strategy_code,
                parameters=parameters,
                risk_indicators=data.get("risk_indicators", {}),
                expected_performance=data.get("expected_performance", {}),
                reasoning=data.get("reasoning"),
                confidence_score=data.get("confidence_score", 0.8),
            )

        except Exception as e:
            self.logger.warning(f"Failed to parse Claude response: {e}")
            # 返回基本响应
            return StrategyResponse(
                strategy_name="Claude Generated Strategy",
                description=content,
                strategy_type=request.strategy_type or self._parse_strategy_type("custom"),
                complexity_level=request.complexity_level,
                code=StrategyCode(language="python", code=content, dependencies=["pandas", "numpy"]),
                model_used=self.config.model_name,
                confidence_score=0.7,
            )

    def _parse_strategy_type(self, type_str: str):
        """解析策略类型"""
        from .base import StrategyType

        type_mapping = {
            "momentum": StrategyType.MOMENTUM,
            "mean_reversion": StrategyType.MEAN_REVERSION,
            "arbitrage": StrategyType.ARBITRAGE,
            "trend_following": StrategyType.TREND_FOLLOWING,
            "breakout": StrategyType.BREAKOUT,
            "custom": StrategyType.CUSTOM,
        }

        return type_mapping.get(type_str.lower(), StrategyType.CUSTOM)

    def _parse_complexity_level(self, level_str: str):
        """解析复杂度级别"""
        from .base import ComplexityLevel

        level_mapping = {
            "basic": ComplexityLevel.BASIC,
            "intermediate": ComplexityLevel.INTERMEDIATE,
            "advanced": ComplexityLevel.ADVANCED,
            "expert": ComplexityLevel.EXPERT,
        }

        return level_mapping.get(level_str.lower(), ComplexityLevel.INTERMEDIATE)
