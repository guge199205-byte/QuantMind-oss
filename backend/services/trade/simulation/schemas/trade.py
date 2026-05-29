"""
Simulation trade schemas.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import UUID4, BaseModel, ConfigDict, Field

from backend.services.trade.simulation.models.order import OrderSide, TradingMode


class SimTradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trade_id: UUID4
    order_id: UUID4
    tenant_id: str
    user_id: int
    portfolio_id: int
    symbol: str
    side: OrderSide
    trading_mode: TradingMode
    quantity: float
    price: float
    trade_value: float
    commission: float
    executed_at: datetime
    price_source: str | None
    created_at: datetime
    updated_at: datetime


class TradeStatsDailyPoint(BaseModel):
    timestamp: str
    value: int
    label: str = "trade_count"


class SimTradeStatsResponse(BaseModel):
    daily_counts: list[TradeStatsDailyPoint] = Field(default_factory=list)
    total_trades: int
    total_value: float
    total_commission: float
    buy_trades: int
    sell_trades: int


class SimTradeListQuery(BaseModel):
    portfolio_id: int | None = None
    symbol: str | None = None
    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)
