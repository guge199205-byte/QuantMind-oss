#!/usr/bin/env python3
"""
LLM查询解析器

使用大语言模型(LLM)解析用户的自然语言查询,
将其转换为结构化的股票筛选参数。

支持OpenAI GPT-4/3.5、Claude等LLM。

Author: QuantMind Team
Version: 1.0.0
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

try:
    import openai
except ImportError:
    openai = None

logger = logging.getLogger(__name__)


@dataclass
class ScreenCondition:
    """筛选条件"""

    type: str  # 条件类型
    operator: str | None = None  # 操作符
    value: Any | None = None  # 值
    unit: str | None = None  # 单位

    # 扩展字段
    min_value: float | None = None
    max_value: float | None = None
    categories: list[str] | None = None
    mode: str | None = None  # include/exclude
    direction: str | None = None  # increasing/decreasing
    days: int | None = None

    def to_dict(self) -> dict:
        """转换为字典,排除None值"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ParsedQuery:
    """解析后的查询"""

    conditions: list[ScreenCondition]
    limit: int = 50
    sort_by: str | None = None
    sort_order: str = "asc"
    explanation: str | None = None  # 解析说明

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "conditions": [c.to_dict() for c in self.conditions],
            "limit": self.limit,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order,
            "explanation": self.explanation,
        }


class LLMQueryParser:
    """LLM查询解析器

    使用大语言模型解析用户的自然语言查询。
    支持多种LLM提供商和模型。
    """

    # 系统提示词
    SYSTEM_PROMPT = """你是一个专业的股票筛选助手。用户会用自然语言描述选股条件，你需要将其转换为结构化的查询参数。

支持的筛选条件类型:
1. market_cap: 市值筛选 (单位: 亿元)
   - 示例: "市值小于300亿" → {"type": "market_cap", "max_value": 300}

2. pe_ratio: 市盈率
   - 示例: "PE低于20" → {"type": "pe_ratio", "max_value": 20}

3. pb_ratio: 市净率
   - 示例: "PB在1到3之间" → {"type": "pb_ratio", "min_value": 1, "max_value": 3}

4. float_ratio: 流通股比例 (单位: %)
   - 示例: "流通股比例小于30%" → {"type": "float_ratio", "max_value": 30}

5. volume_trend: 成交量趋势
   - 示例: "近3天成交量持续走高" → {"type": "volume_trend", "direction": "increasing", "days": 3}

6. price_range: 价格区间
   - 示例: "价格在5到50元之间" → {"type": "price_range", "min_value": 5, "max_value": 50}

7. industry: 行业分类
   - 示例: "科技股" → {"type": "industry", "categories": ["计算机", "电子", "通信", "软件"], "mode": "include"}
   - 示例: "排除金融股" → {"type": "industry", "categories": ["银行", "保险", "券商"], "mode": "exclude"}

8. market: 市场
   - 示例: "沪深市场" → {"type": "market", "categories": ["SH", "SZ"], "mode": "include"}

9. roe: 净资产收益率 (单位: %)
   - 示例: "ROE大于15%" → {"type": "roe", "min_value": 15}

10. revenue_growth: 营收增长率 (单位: %)
    - 示例: "营收增长率超过20%" → {"type": "revenue_growth", "min_value": 20}

11. change_pct: 涨跌幅 (单位: %)
    - 示例: "近一周涨幅超过5%" → {"type": "change_pct", "min_value": 5, "days": 5}

行业关键词映射:
- 科技股 → 计算机、电子、通信、软件服务、半导体
- 金融股 → 银行、保险、券商、信托
- 医药股 → 医药生物、医疗器械、中药
- 消费股 → 食品饮料、纺织服装、商业贸易
- 地产股 → 房地产、建筑材料、建筑装饰
- 新能源 → 电力设备、新能源、汽车

市场代码:
- 上交所: SH
- 深交所: SZ
- 北交所: BJ

输出格式要求:
1. 必须返回JSON格式
2. conditions是数组,包含所有提取的条件
3. limit默认50,最大1000
4. sort_by可选值: market_cap, pe_ratio, change_pct等
5. sort_order: asc或desc
6. explanation: 用一句话解释解析结果

示例输出:
{
  "conditions": [
    {"type": "market_cap", "max_value": 300},
    {"type": "industry", "categories": ["计算机", "电子"], "mode": "include"}
  ],
  "limit": 50,
  "sort_by": "market_cap",
  "sort_order": "asc",
  "explanation": "筛选市值小于300亿的计算机和电子行业股票"
}

注意事项:
1. 如果用户没有明确指定数值,使用合理的默认值
2. "小于"用max_value,"大于"用min_value
3. 行业描述要转换为具体的行业名称
4. 不确定的条件可以省略,不要猜测
5. 保持解释简洁明了
"""

    def __init__(
        self,
        api_key: str = None,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.3,
    ):
        """初始化LLM解析器

        Args:
            api_key: OpenAI API Key
            model: 模型名称
            temperature: 温度参数 (0-1,越低越确定)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.temperature = temperature

        if openai and self.api_key:
            openai.api_key = self.api_key
            self._available = True
            logger.info(f"LLM解析器初始化成功: {model}")
        else:
            self._available = False
            logger.warning("LLM解析器不可用: 缺少openai或API key")

    def is_available(self) -> bool:
        """检查LLM是否可用"""
        return self._available and openai is not None

    def parse(self, user_query: str) -> ParsedQuery:
        """解析用户查询

        Args:
            user_query: 用户的自然语言查询

        Returns:
            ParsedQuery: 解析后的结构化查询
        """
        if not self.is_available():
            logger.warning("LLM不可用,返回空查询")
            return ParsedQuery(conditions=[], explanation="LLM服务不可用")

        try:
            logger.info(f"开始解析查询: {user_query}")

            # 调用OpenAI API
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_query},
                ],
                temperature=self.temperature,
                max_tokens=1000,
            )

            # 提取响应
            content = response.choices[0].message.content
            logger.debug(f"LLM响应: {content}")

            # 解析JSON
            parsed_data = self._parse_json_response(content)

            # 转换为ParsedQuery对象
            result = self._convert_to_parsed_query(parsed_data, user_query)

            logger.info(f"解析成功: {len(result.conditions)} 个条件")
            return result

        except Exception as e:
            logger.error(f"解析失败: {e}", exc_info=True)
            return ParsedQuery(conditions=[], explanation=f"解析失败: {str(e)}")

    def _parse_json_response(self, content: str) -> dict:
        """解析LLM返回的JSON

        Args:
            content: LLM返回的文本

        Returns:
            解析后的字典
        """
        # 尝试提取JSON (可能包含其他文本)
        try:
            # 直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取JSON块
            start_idx = content.find("{")
            end_idx = content.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                return json.loads(json_str)
            else:
                raise ValueError("无法从响应中提取JSON")

    def _convert_to_parsed_query(self, data: dict, original_query: str) -> ParsedQuery:
        """将字典转换为ParsedQuery对象

        Args:
            data: 解析的字典数据
            original_query: 原始查询

        Returns:
            ParsedQuery对象
        """
        conditions = []

        for cond_data in data.get("conditions", []):
            condition = ScreenCondition(
                type=cond_data.get("type"),
                operator=cond_data.get("operator"),
                value=cond_data.get("value"),
                unit=cond_data.get("unit"),
                min_value=cond_data.get("min_value"),
                max_value=cond_data.get("max_value"),
                categories=cond_data.get("categories"),
                mode=cond_data.get("mode"),
                direction=cond_data.get("direction"),
                days=cond_data.get("days"),
            )
            conditions.append(condition)

        return ParsedQuery(
            conditions=conditions,
            limit=data.get("limit", 50),
            sort_by=data.get("sort_by"),
            sort_order=data.get("sort_order", "asc"),
            explanation=data.get("explanation", f"解析查询: {original_query}"),
        )

    def parse_with_function_calling(self, user_query: str) -> ParsedQuery:
        """使用Function Calling方式解析

        这是OpenAI推荐的结构化输出方式,更可靠。

        Args:
            user_query: 用户查询

        Returns:
            ParsedQuery对象
        """
        if not self.is_available():
            return ParsedQuery(conditions=[], explanation="LLM服务不可用")

        # 定义Function
        functions = [
            {
                "name": "screen_stocks",
                "description": "根据条件筛选股票",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "conditions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "min_value": {"type": "number"},
                                    "max_value": {"type": "number"},
                                    "categories": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "mode": {"type": "string"},
                                    "direction": {"type": "string"},
                                    "days": {"type": "integer"},
                                },
                                "required": ["type"],
                            },
                        },
                        "limit": {"type": "integer"},
                        "sort_by": {"type": "string"},
                        "sort_order": {"type": "string"},
                        "explanation": {"type": "string"},
                    },
                    "required": ["conditions"],
                },
            }
        ]

        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_query},
                ],
                functions=functions,
                function_call={"name": "screen_stocks"},
                temperature=self.temperature,
            )

            # 提取函数参数
            function_args = response.choices[0].message.function_call.arguments
            data = json.loads(function_args)

            return self._convert_to_parsed_query(data, user_query)

        except Exception as e:
            logger.error(f"Function calling解析失败: {e}")
            # 降级到普通解析
            return self.parse(user_query)


# 单例实例
_llm_parser = None


def get_llm_parser(api_key: str = None, model: str = "gpt-3.5-turbo") -> LLMQueryParser:
    """获取LLM解析器单例

    Args:
        api_key: OpenAI API key
        model: 模型名称

    Returns:
        LLMQueryParser实例
    """
    global _llm_parser
    if _llm_parser is None:
        _llm_parser = LLMQueryParser(api_key=api_key, model=model)
    return _llm_parser
