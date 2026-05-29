"""Symbol schemas"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SymbolBase(BaseModel):
    """交易标的基础模型"""

    symbol: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    exchange: str = Field(..., description="交易所 (SH/SZ/HK/US)")
    market: str = Field(..., description="市场类型 (A股/港股/美股)")
    sector: str | None = Field(None, description="行业板块")
    is_active: bool = Field(True, description="是否活跃")


class SymbolCreate(SymbolBase):
    """创建交易标的"""


class SymbolResponse(SymbolBase):
    """交易标的响应"""

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    updated_at: datetime


class SymbolListResponse(BaseModel):
    """交易标的列表响应"""

    total: int
    symbols: list[SymbolResponse]
