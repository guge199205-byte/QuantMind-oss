"""KLine schemas"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class KLineBase(BaseModel):
    """K线基础模型"""

    symbol: str = Field(..., description="股票代码")
    interval: str = Field(..., description="时间周期 (1m/5m/15m/30m/1h/4h/1d/1w/1M)")
    timestamp: datetime = Field(..., description="K线时间")
    open_price: float = Field(..., description="开盘价")
    high_price: float = Field(..., description="最高价")
    low_price: float = Field(..., description="最低价")
    close_price: float = Field(..., description="收盘价")
    volume: int = Field(..., description="成交量")
    amount: float | None = Field(None, description="成交额")
    change: float | None = Field(None, description="涨跌额")
    change_percent: float | None = Field(None, description="涨跌幅%")
    turnover_rate: float | None = Field(None, description="换手率%")
    data_source: str | None = Field(None, description="数据源")


class KLineCreate(KLineBase):
    """创建K线"""


class KLineResponse(KLineBase):
    """K线响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class KLineListResponse(BaseModel):
    """K线列表响应"""

    total: int
    klines: list[KLineResponse]
