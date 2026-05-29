from __future__ import annotations

import time
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _ts_ms() -> int:
    return int(time.time() * 1000)


class SignalCreatedEvent(BaseModel):
    event_type: Literal["signal_created"] = "signal_created"
    schema_version: str = "1.0"
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    ts_ms: int = Field(default_factory=_ts_ms)

    tenant_id: str
    user_id: str
    strategy_id: str | None = None
    run_id: str
    trace_id: str | None = None

    signal_id: str
    client_order_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    trade_action: str | None = None
    position_side: str | None = None
    is_margin_trade: bool | None = None
    quantity: int
    price: float
    score: float
    signal_source: Literal["fusion_report", "inference_fallback"] = "fusion_report"


class ExecutionEvent(BaseModel):
    event_type: Literal[
        "order_submitted",
        "order_filled",
        "order_rejected",
        "order_duplicate_skipped",
    ]
    schema_version: str = "1.0"
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    ts_ms: int = Field(default_factory=_ts_ms)

    tenant_id: str
    user_id: str
    strategy_id: str | None = None
    trace_id: str | None = None

    signal_id: str | None = None
    client_order_id: str | None = None
    broker_order_id: str | None = None
    exec_id: str | None = None

    status: str
    symbol: str | None = None
    side: str | None = None
    quantity: float | None = None
    filled_qty: float | None = None
    price: float | None = None
    filled_price: float | None = None
    reason: str | None = None
