from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, Index, Integer, JSON, String, UniqueConstraint

from backend.services.trade.models.base import Base


class RealAccountLedgerDailySnapshot(Base):
    __tablename__ = "real_account_ledger_daily_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "account_id",
            "snapshot_date",
            name="uq_real_account_ledger_daily",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    account_id = Column(String(64), nullable=False, index=True)

    snapshot_date = Column(Date, nullable=False, index=True)
    last_snapshot_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    initial_equity = Column(Float, nullable=False, default=0.0)
    day_open_equity = Column(Float, nullable=False, default=0.0)
    month_open_equity = Column(Float, nullable=False, default=0.0)
    total_asset = Column(Float, nullable=False, default=0.0)
    cash = Column(Float, nullable=False, default=0.0)
    market_value = Column(Float, nullable=False, default=0.0)
    today_pnl_raw = Column(Float, nullable=False, default=0.0)
    monthly_pnl_raw = Column(Float, nullable=False, default=0.0)
    total_pnl_raw = Column(Float, nullable=False, default=0.0)
    floating_pnl_raw = Column(Float, nullable=False, default=0.0)
    daily_return_pct = Column(Float, nullable=False, default=0.0)
    total_return_pct = Column(Float, nullable=False, default=0.0)
    position_count = Column(Integer, nullable=False, default=0)
    source = Column(String(32), nullable=False, default="qmt_bridge")
    payload_json = Column(JSON, nullable=False, default=dict)


Index(
    "ix_real_account_ledger_daily_scope_date",
    RealAccountLedgerDailySnapshot.tenant_id,
    RealAccountLedgerDailySnapshot.user_id,
    RealAccountLedgerDailySnapshot.account_id,
    RealAccountLedgerDailySnapshot.snapshot_date,
)
