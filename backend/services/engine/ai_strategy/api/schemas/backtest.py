"""AI 策略向导 - 回测相关 Schema 定义"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class BacktestRequest(BaseModel):
    strategy_config: dict[str, Any]
    symbols: list[str]
    start_date: str
    end_date: str
    force_provider: str | None = None


class BacktestResponse(BaseModel):
    success: bool
    data: dict[str, Any]
    provider: str
    elapsed_ms: float
    fallback: bool = False
