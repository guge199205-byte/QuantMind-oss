from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class QMTBridgeSessionRequest(BaseModel):
    access_key: str
    secret_key: str
    agent_type: str = Field(default="qmt")
    account_id: str
    client_fingerprint: str
    client_version: str | None = None
    hostname: str | None = None
    force_rebind: bool = Field(
        default=False,
        description="强制覆盖旧设备绑定（client_fingerprint 冲突时使用）",
    )


class QMTBridgeSessionResponse(BaseModel):
    bridge_session_token: str
    expires_in: int
    ws_url: str
    tenant_id: str
    user_id: str
    permissions: list[str]
    binding: dict[str, Any]


class QMTBridgeRefreshResponse(BaseModel):
    bridge_session_token: str
    expires_in: int


class QMTPositionPayload(BaseModel):
    symbol: str
    symbol_name: str | None = None
    volume: int = 0
    available_volume: int = 0
    cost_price: float = 0.0
    last_price: float = 0.0
    market_value: float = 0.0


class QMTBridgeAccountPayload(BaseModel):
    account_id: str
    broker: str = "qmt"
    cash: float = 0.0
    available_cash: float = 0.0
    frozen_cash: float = 0.0
    short_proceeds: float = 0.0
    liabilities: float = 0.0
    short_market_value: float = 0.0
    credit_limit: float = 0.0
    maintenance_margin_ratio: float = 0.0
    credit_enabled: bool = False
    shortable_symbols_count: int = 0
    last_short_check_at: float | None = None
    total_asset: float = 0.0
    market_value: float = 0.0
    today_pnl: float = 0.0
    total_pnl: float = 0.0
    floating_pnl: float = 0.0
    yesterday_balance: float = 0.0
    positions: list[QMTPositionPayload] = Field(default_factory=list)
    compacts: list[dict[str, Any]] = Field(default_factory=list)
    credit_subjects: list[dict[str, Any]] = Field(default_factory=list)
    debug_version: str | None = None
    reported_at: datetime | None = None


class QMTBridgeHeartbeatPayload(BaseModel):
    account_id: str
    client_version: str | None = None
    hostname: str | None = None
    status: str = "running"
    qmt_connected: bool = True
    latency_ms: int | None = None
    reported_at: datetime | None = None


class QMTBridgeExecutionPayload(BaseModel):
    client_order_id: str
    exchange_order_id: str | None = None
    exchange_trade_id: str | None = None
    account_id: str
    symbol: str
    side: str
    status: str
    filled_quantity: float = 0.0
    filled_price: float | None = None
    error_code: str | None = None
    message: str | None = None
    reported_at: datetime | None = None


class QMTBindingStatusResponse(BaseModel):
    online: bool
    user_id: str
    tenant_id: str
    account_id: str | None = None
    hostname: str | None = None
    client_version: str | None = None
    last_seen_at: str | None = None
    heartbeat_at: str | None = None
    account_reported_at: str | None = None
    stale_reason: str | None = None


class QMTAgentDownloadAssetInfo(BaseModel):
    asset: str
    key: str
    file_name: str
    download_url: str
    sha256: str | None = None
    content_type: str | None = None
    expires_in: int


class QMTAgentReleaseDownloadResponse(BaseModel):
    product: str = "QuantMindQMTAgent"
    channel: str = "release"
    version: str
    build_time: str | None = None
    manifest_key: str | None = None
    manifest_url: str | None = None
    selected_asset: str
    installer: QMTAgentDownloadAssetInfo | None = None
    portable: QMTAgentDownloadAssetInfo | None = None
