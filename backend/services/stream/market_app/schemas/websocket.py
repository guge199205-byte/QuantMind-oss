"""WebSocket schemas"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WSMessage(BaseModel):
    """WebSocket消息"""

    type: str = Field(..., description="消息类型 (quote/kline/heartbeat/error)")
    data: dict[str, Any] | None = Field(None, description="消息数据")
    timestamp: float = Field(..., description="时间戳")


class WSSubscribe(BaseModel):
    """WebSocket订阅"""

    action: str = Field("subscribe", description="操作类型")
    symbols: list[str] = Field(..., description="股票代码列表")
    data_type: str = Field("quote", description="数据类型 (quote/kline)")
    interval: str | None = Field(None, description="K线周期 (仅data_type=kline时)")


class WSUnsubscribe(BaseModel):
    """WebSocket取消订阅"""

    action: str = Field("unsubscribe", description="操作类型")
    symbols: list[str] = Field(..., description="股票代码列表")
