"""
Local Provider实现 (Ollama, LocalAI等)
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

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


class LocalProvider(BaseAIProvider):
    """Local Provider (支持Ollama, LocalAI等本地模型)"""

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.client: AsyncOpenAI | None = None
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    async def initialize(self) -> bool:
        """初始化本地模型客户端"""
        try:
            # 默认使用Ollama的API地址
            api_base = self.config.api_base or "http://localhost:11434/v1"

            self.client = AsyncOpenAI(
                api_key=self.config.api_key or "not-required",  # 本地模型通常不需要API key
                base_url=api_base,
                timeout=self.config.timeout,
                max_retries=self.config.retry_attempts,
            )

            # 测试连接
            await self._test_connection()
            self._is_initialized = True

            self.logger.info(
                "Local provider initialized successfully",
                model=self.config.model_name,
                api_base=api_base,
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize Local provider: {e}")
            return False

    async def _test_connection(self):
        """测试连接"""
        try:
            await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return True
        except Exception as e:
            raise Exception(f"Local model connection test failed: {e}")

    async def generate_strategy(self, request: StrategyRequest) -> StrategyResponse:
        """生成交易策略"""
        if not self._is_initialized:
            raise RuntimeError("Local provider not initialized")

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
    "confidence_score": 0.75
}}

注意：
- 本地模型可能需要更明确的指令
- 请确保JSON格式正确
- 代码要完整可执行
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            response = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                **self.config.custom_params,
            )

            content = response.choices[0].message.content

            # 本地模型通常不提供token使用统计
            estimated_tokens = self.estimate_tokens(system_prompt + user_prompt + content)
            token_usage = {
                "prompt_tokens": estimated_tokens // 2,
                "completion_tokens": estimated_tokens // 2,
                "total_tokens": estimated_tokens,
            }

            # 解析响应
            strategy_response = self._parse_local_response(content, request)
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
            raise RuntimeError("Local provider not initialized")

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

请提供优化后的策略，重点关注：
1. 提高策略性能
2. 降低风险
3. 优化参数
4. 改进代码质量

请按照相同的JSON格式返回优化结果。
"""

            messages = [
                {"role": "system", "content": "你是一个专业的量化交易策略优化专家。"},
                {"role": "user", "content": prompt},
            ]

            response = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            content = response.choices[0].message.content

            # 创建一个基本的请求对象用于解析
            dummy_request = StrategyRequest(
                prompt="Strategy optimization",
                complexity_level=(self.config.complexity_level if hasattr(self.config, "complexity_level") else None),
            )

            optimized_response = self._parse_local_response(content, dummy_request)
            optimized_response.model_used = self.config.model_name

            return optimized_response

        except Exception as e:
            self.logger.error(f"Failed to optimize strategy: {e}")
            raise

    async def analyze_strategy(self, strategy_code: str) -> dict[str, Any]:
        """分析策略代码"""
        if not self._is_initialized:
            raise RuntimeError("Local provider not initialized")

        try:
            prompt = f"""
请分析以下量化交易策略代码：

```python
{strategy_code}
```

请提供详细分析，包括：
1. 策略逻辑概述
2. 潜在风险点
3. 性能瓶颈
4. 改进建议
5. 代码质量评分

请以JSON格式返回分析结果。
"""

            messages = [
                {"role": "system", "content": "你是一个专业的量化交易策略分析师。"},
                {"role": "user", "content": prompt},
            ]

            response = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=0.3,
            )

            content = response.choices[0].message.content

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
            raise RuntimeError("Local provider not initialized")

        try:
            prompt = f"""
请验证以下量化交易策略代码：

```python
{strategy_code}
```

请检查：
1. 语法错误
2. 逻辑错误
3. 潜在风险
4. 性能问题

请以JSON格式返回验证结果。
"""

            messages = [
                {"role": "system", "content": "你是一个专业的代码验证专家。"},
                {"role": "user", "content": prompt},
            ]

            response = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=0.1,
            )

            content = response.choices[0].message.content

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
        return [ModelType.LOCAL_LLAMA, ModelType.LOCAL_MISTRAL, ModelType.CUSTOM]

    def estimate_tokens(self, text: str) -> int:
        """估算token数量"""
        # 本地模型的token估算
        return len(text) // 4

    def _parse_local_response(self, content: str, request: StrategyRequest) -> StrategyResponse:
        """解析本地模型响应"""
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
                    "strategy_name": "Local Model Generated Strategy",
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
                    "confidence_score": 0.6,
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
                strategy_name=data.get("strategy_name", "Local Model Generated Strategy"),
                description=data.get("description", ""),
                strategy_type=strategy_type,
                complexity_level=complexity,
                code=strategy_code,
                parameters=parameters,
                risk_indicators=data.get("risk_indicators", {}),
                expected_performance=data.get("expected_performance", {}),
                reasoning=data.get("reasoning"),
                confidence_score=data.get("confidence_score", 0.6),
            )

        except Exception as e:
            self.logger.warning(f"Failed to parse local model response: {e}")
            # 返回基本响应
            return StrategyResponse(
                strategy_name="Local Model Generated Strategy",
                description=content,
                strategy_type=request.strategy_type or self._parse_strategy_type("custom"),
                complexity_level=request.complexity_level,
                code=StrategyCode(language="python", code=content, dependencies=["pandas", "numpy"]),
                model_used=self.config.model_name,
                confidence_score=0.5,
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
