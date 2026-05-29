"""Quote schemas"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class QuoteBase(BaseModel):
    """实时行情基础模型"""

    symbol: str = Field(..., description="股票代码")
    timestamp: datetime = Field(..., description="行情时间")
    current_price: float = Field(..., description="当前价")
    open_price: float | None = Field(None, description="开盘价")
    high_price: float | None = Field(None, description="最高价")
    low_price: float | None = Field(None, description="最低价")
    close_price: float | None = Field(None, description="收盘价")
    volume: int | None = Field(None, description="成交量")
    amount: float | None = Field(None, description="成交额")
    pre_close: float | None = Field(None, description="昨收价")
    change: float | None = Field(None, description="涨跌额")
    change_percent: float | None = Field(None, description="涨跌幅%")
    change_percent: float | None = Field(None, description="涨跌幅%")

    # Level 5 Quote Data
    bid1_price: float | None = Field(None, description="买一价")
    bid1_volume: int | None = Field(None, description="买一量")
    bid2_price: float | None = Field(None, description="买二价")
    bid2_volume: int | None = Field(None, description="买二量")
    bid3_price: float | None = Field(None, description="买三价")
    bid3_volume: int | None = Field(None, description="买三量")
    bid4_price: float | None = Field(None, description="买四价")
    bid4_volume: int | None = Field(None, description="买四量")
    bid5_price: float | None = Field(None, description="买五价")
    bid5_volume: int | None = Field(None, description="买五量")

    ask1_price: float | None = Field(None, description="卖一价")
    ask1_volume: int | None = Field(None, description="卖一量")
    ask2_price: float | None = Field(None, description="卖二价")
    ask2_volume: int | None = Field(None, description="卖二量")
    ask3_price: float | None = Field(None, description="卖三价")
    ask3_volume: int | None = Field(None, description="卖三量")
    ask4_price: float | None = Field(None, description="卖四价")
    ask4_volume: int | None = Field(None, description="卖四量")
    ask5_price: float | None = Field(None, description="卖五价")
    ask5_volume: int | None = Field(None, description="卖五量")
    data_source: str | None = Field(None, description="数据源")
    is_stale: bool = Field(False, description="数据是否陈旧(超过更新频率)")


class QuoteCreate(QuoteBase):
    """创建行情"""


class QuoteResponse(QuoteBase):
    """行情响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class QuoteListResponse(BaseModel):
    """行情列表响应"""

    total: int
    quotes: list[QuoteResponse]
