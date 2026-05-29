from datetime import datetime

from sqlalchemy import JSON, Column, Date, DateTime, Float, Index, Integer, String

from backend.services.trade.models.base import Base


class RealAccountSnapshot(Base):
    __tablename__ = "real_account_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(50), nullable=False, index=True)
    user_id = Column(String(50), nullable=False, index=True)
    account_id = Column(String(64), nullable=False, index=True)

    snapshot_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    snapshot_month = Column(String(7), nullable=False, index=True)  # YYYY-MM

    total_asset = Column(Float, nullable=False, default=0.0)
    cash = Column(Float, nullable=False, default=0.0)
    market_value = Column(Float, nullable=False, default=0.0)

    today_pnl_raw = Column(Float, nullable=False, default=0.0)
    total_pnl_raw = Column(Float, nullable=False, default=0.0)
    floating_pnl_raw = Column(Float, nullable=False, default=0.0)

    source = Column(String(32), nullable=False, default="qmt_bridge")
    payload_json = Column(JSON, nullable=False, default=dict)


Index(
    "ix_real_account_snapshots_scope_time",
    RealAccountSnapshot.tenant_id,
    RealAccountSnapshot.user_id,
    RealAccountSnapshot.account_id,
    RealAccountSnapshot.snapshot_at,
)

Index(
    "ix_real_account_snapshots_scope_date_time",
    RealAccountSnapshot.tenant_id,
    RealAccountSnapshot.user_id,
    RealAccountSnapshot.account_id,
    RealAccountSnapshot.snapshot_date,
    RealAccountSnapshot.snapshot_at,
)

Index(
    "ix_real_account_snapshots_scope_month_time",
    RealAccountSnapshot.tenant_id,
    RealAccountSnapshot.user_id,
    RealAccountSnapshot.account_id,
    RealAccountSnapshot.snapshot_month,
    RealAccountSnapshot.snapshot_at,
)
