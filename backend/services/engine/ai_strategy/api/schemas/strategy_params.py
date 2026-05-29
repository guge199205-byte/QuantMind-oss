"""AI 策略向导 - 策略参数相关 Schema 定义"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BuyRule(BaseModel):
    kind: str
    name: str
    params: dict[str, Any] | None = None
    priority: int | None = None
    weight: float | None = None


class SellRule(BaseModel):
    kind: str
    name: str
    params: dict[str, Any] | None = None


class RiskConfig(BaseModel):
    rebalanceFrequency: str | None = None
    maxDrawdown: float | None = None
    maxPositionSize: float | None = None
    maxPositions: int | None = None
    riskFreeRate: float | None = None
    effectiveFrom: str | None = None
    effectiveTo: str | None = None


class PositionConfig(BaseModel):
    enableDynamicPosition: bool = False
    bearMarketPosition: float = 0.4
    normalMarketPosition: float = 0.6
    bullMarketPosition: float = 0.9
    strategyTotalPosition: float = 0.5
    marketIndexSymbol: str | None = "000300"
    detectionWindow: int | None = 20
    volumeThreshold: float | None = 0.2


class ValidatePositionRequest(BaseModel):
    position_config: PositionConfig
    stock_pool_size: int = Field(0, ge=0)


class ValidatePositionResponse(BaseModel):
    valid: bool
    warnings: list[str] = []
    estimated_stock_count: dict[str, int]
