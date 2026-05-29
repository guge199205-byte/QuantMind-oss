"""Pydantic schemas for trade portfolio module."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.services.trade.models.enums import PositionSide, TradeAction


class PortfolioBase(BaseModel):
    name: str = Field(..., max_length=100, description="组合名称")
    description: str | None = Field(None, description="组合描述")
    initial_capital: Decimal = Field(..., ge=0, description="初始资金")


class PortfolioCreate(PortfolioBase):
    tenant_id: str = Field("default", max_length=64, description="租户ID")
    user_id: int = Field(..., description="用户ID")


class PortfolioUpdate(BaseModel):
    name: str | None = Field(None, max_length=100, description="组合名称")
    description: str | None = Field(None, description="组合描述")
    status: str | None = Field(None, description="状态")


class PortfolioResponse(PortfolioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: str
    user_id: int
    current_capital: Decimal
    available_cash: Decimal
    frozen_cash: Decimal
    total_value: Decimal
    total_pnl: Decimal
    total_return: Decimal
    daily_pnl: Decimal
    daily_return: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Decimal | None
    volatility: Decimal | None
    status: str
    created_at: datetime
    updated_at: datetime


class PortfolioSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    total_value: Decimal
    total_pnl: Decimal
    total_return: Decimal
    status: str
    position_count: int = 0


class PositionBase(BaseModel):
    symbol: str = Field(..., max_length=20, description="证券代码")
    symbol_name: str | None = Field(
        None, max_length=100, description="证券名称")
    exchange: str | None = Field(None, max_length=20, description="交易所")


class PositionCreate(PositionBase):
    quantity: int = Field(..., gt=0, description="数量")
    price: Decimal = Field(..., gt=0, description="价格")


class PositionUpdate(BaseModel):
    quantity: int | None = Field(None, ge=0, description="数量")
    current_price: Decimal | None = Field(None, ge=0, description="当前价格")
    status: str | None = Field(None, description="状态")


class PositionAdjust(BaseModel):
    action: str = Field(..., description="操作: add, reduce")
    quantity: int = Field(..., gt=0, description="数量")
    price: Decimal = Field(..., gt=0, description="价格")
    note: str | None = Field(None, description="备注")


class TradeSync(BaseModel):
    portfolio_id: int = Field(..., gt=0, description="组合ID")
    symbol: str = Field(..., max_length=20, description="证券代码")
    side: str = Field(..., description="买卖方向: buy, sell")
    quantity: int = Field(..., gt=0, description="数量")
    price: Decimal = Field(..., gt=0, description="价格")
    commission: Decimal = Field(0, ge=0, description="佣金")
    stamp_duty: Decimal = Field(0, ge=0, description="印花税")
    transfer_fee: Decimal = Field(0, ge=0, description="过户费")
    total_fee: Decimal | None = Field(None, description="总费用")
    position_side: PositionSide | None = Field(None, description="持仓方向")
    trade_action: TradeAction | None = Field(None, description="操作类型")
    trade_id: str | None = Field(None, description="交易ID")


class PositionResponse(PositionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    quantity: int
    available_quantity: int
    frozen_quantity: int
    avg_cost: Decimal
    total_cost: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_rate: Decimal
    realized_pnl: Decimal
    weight: Decimal
    status: str
    opened_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class PositionHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position_id: int
    action: str
    quantity_change: int
    price: Decimal
    amount: Decimal
    quantity_after: int
    avg_cost_after: Decimal
    note: str | None
    created_at: datetime


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    snapshot_date: datetime
    total_value: Decimal
    available_cash: Decimal
    market_value: Decimal
    total_pnl: Decimal
    total_return: Decimal
    daily_pnl: Decimal
    daily_return: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Decimal | None
    volatility: Decimal | None
    position_count: int
    created_at: datetime


class PerformanceMetrics(BaseModel):
    total_return: Decimal = Field(..., description="总收益率")
    annual_return: Decimal = Field(..., description="年化收益率")
    max_drawdown: Decimal = Field(..., description="最大回撤")
    sharpe_ratio: Decimal | None = Field(None, description="夏普比率")
    sortino_ratio: Decimal | None = Field(None, description="索提诺比率")
    volatility: Decimal | None = Field(None, description="波动率")
    win_rate: Decimal = Field(..., description="胜率")
    profit_factor: Decimal = Field(..., description="盈亏比")
    total_trades: int = Field(..., description="总交易次数")
    winning_trades: int = Field(..., description="盈利交易次数")
    losing_trades: int = Field(..., description="亏损交易次数")


class PerformanceResponse(BaseModel):
    portfolio_id: int
    metrics: PerformanceMetrics
    snapshots: list[SnapshotResponse] = []


class BindStrategyRequest(BaseModel):
    strategy_id: int = Field(..., gt=0, description="策略ID")


class RealTradingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    strategy_id: int | None
    real_trading_id: str | None
    run_status: str
    status: str
    total_value: Decimal
    updated_at: datetime


class MessageResponse(BaseModel):
    message: str
    code: int = 200


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list
