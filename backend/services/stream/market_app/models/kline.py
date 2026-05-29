"""KLine model for OHLCV data"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, UniqueConstraint

from .base import Base


class KLine(Base):
    """K线数据表"""

    __tablename__ = "klines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True, comment="股票代码")
    interval = Column(
        String(10), nullable=False, comment="时间周期 (1m/5m/15m/30m/1h/4h/1d/1w/1M)"
    )
    timestamp = Column(DateTime, nullable=False, comment="K线时间")

    # OHLCV data
    open_price = Column(Float, nullable=False, comment="开盘价")
    high_price = Column(Float, nullable=False, comment="最高价")
    low_price = Column(Float, nullable=False, comment="最低价")
    close_price = Column(Float, nullable=False, comment="收盘价")
    volume = Column(Integer, nullable=False, comment="成交量")
    amount = Column(Float, comment="成交额")

    # Additional data
    change = Column(Float, comment="涨跌额")
    change_percent = Column(Float, comment="涨跌幅%")
    turnover_rate = Column(Float, comment="换手率%")

    # Metadata
    data_source = Column(String(20), comment="数据源")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "symbol", "interval", "timestamp", name="uq_symbol_interval_timestamp"
        ),
        Index("idx_symbol_interval_timestamp", "symbol", "interval", "timestamp"),
        Index("idx_timestamp", "timestamp"),
    )
