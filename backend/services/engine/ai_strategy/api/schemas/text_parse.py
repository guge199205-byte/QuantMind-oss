"""AI 策略向导 - 文本解析相关 Schema 定义"""

from typing import Any, Dict, List

from pydantic import BaseModel


class ParseTextRequest(BaseModel):
    text: str


class ParseTradeRulesRequest(BaseModel):
    text: str
    type: str  # "buy" or "sell"


class TradeRule(BaseModel):
    kind: str
    name: str
    params: dict[str, Any] = {}


class ParseTradeRulesResponse(BaseModel):
    rules: list[TradeRule]
    suggestions: list[str] = []
