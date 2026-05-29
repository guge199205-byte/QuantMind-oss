from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from datetime import datetime
from backend.services.trade.models.enums import PositionSide, TradeAction

class PortfolioBase(BaseModel):
    name: str
    description: str | None = None
    initial_capital: Decimal = Field(..., max_digits=20, decimal_places=4)

class PortfolioCreate(PortfolioBase):
    tenant_id: str
    user_id: int

class PortfolioUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None

class PortfolioSchema(PortfolioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: str
    user_id: int
    current_capital: Decimal
    available_cash: Decimal
    frozen_cash: Decimal = Decimal("0")
    total_value: Decimal
    total_pnl: Decimal
    daily_pnl: Decimal
    total_return: Decimal
    daily_return: Decimal
    max_drawdown: Decimal
    sharpe_ratio: float | None = None
    volatility: float | None = None
    status: str
    run_status: str
    strategy_id: int | None = None
    real_trading_id: str | None = None
    created_at: datetime
    updated_at: datetime

class PortfolioResponse(PortfolioSchema):
    """跟 PortfolioSchema 一致，用于别名"""
    pass

class PortfolioSummary(BaseModel):
    """投资组合简要汇总"""
    id: int
    name: str
    total_value: Decimal
    total_pnl: Decimal
    total_return: Decimal
    status: str
    position_count: int

class RealTradingResponse(PortfolioSchema):
    """实盘交易响应，结构同 PortfolioSchema"""
    pass

class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str

class SnapshotResponse(BaseModel):
    """组合快照响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    snapshot_date: datetime
    total_value: Decimal
    available_cash: Decimal
    market_value: Decimal | None = None
    total_pnl: Decimal | None = None
    total_return: Decimal | None = None
    daily_pnl: Decimal | None = None
    daily_return: Decimal | None = None
    max_drawdown: Decimal = Decimal("0")
    sharpe_ratio: float | None = None
    volatility: float | None = None
    position_count: int | None = None

class BindStrategyRequest(BaseModel):
    strategy_id: int

# --- Position Schemas ---

class PositionBase(BaseModel):
    symbol: str
    quantity: Decimal
    price: Decimal
    side: str = "long"

class PositionCreate(PositionBase):
    symbol_name: str | None = None
    exchange: str | None = None

class PositionAdjust(BaseModel):
    action: str  # add, reduce
    quantity: Decimal
    price: Decimal
    note: str | None = None

class PositionResponse(PositionBase):
    """一个具体持仓的响应详情"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    avg_price: Decimal
    current_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal = Decimal("0")
    status: str
    weight: Decimal | None = None
    created_at: datetime
    updated_at: datetime

class PositionHistoryResponse(BaseModel):
    """持仓变更历史响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    position_id: int
    action: str
    quantity_change: Decimal
    price: Decimal
    amount: Decimal
    quantity_after: Decimal
    avg_cost_after: Decimal
    note: str | None = None
    created_at: datetime

class TradeSync(BaseModel):
    portfolio_id: int
    symbol: str
    quantity: Decimal
    price: Decimal
    side: str  # buy, sell
    trade_id: str | None = None
    commission: Decimal | None = None
    position_side: PositionSide | None = None
    trade_action: TradeAction | None = None
