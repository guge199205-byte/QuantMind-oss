"""AI 策略向导 - 市场状态相关 Schema 定义"""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class MarketStateResponse(BaseModel):
    """市场状态响应"""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
