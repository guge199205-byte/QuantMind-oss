"""Quote model for real-time market data"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String

from .base import Base


class Quote(Base):
    """实时行情表"""

    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True, comment="股票代码")
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="行情时间（UTC）",
    )

    # Price data
    open_price = Column(Float, comment="开盘价")
    high_price = Column(Float, comment="最高价")
    low_price = Column(Float, comment="最低价")
    close_price = Column(Float, comment="收盘价")
    current_price = Column(Float, nullable=False, comment="当前价")

    # Volume data
    volume = Column(Integer, comment="成交量")
    amount = Column(Float, comment="成交额")

    # Change data
    pre_close = Column(Float, comment="昨收价")
    change = Column(Float, comment="涨跌额")
    change_percent = Column(Float, comment="涨跌幅%")

    # Bid/Ask data
    # Bid/Ask data (Level 5)
    bid1_price = Column(Float, comment="买一价")
    bid1_volume = Column(Integer, comment="买一量")
    bid2_price = Column(Float, comment="买二价")
    bid2_volume = Column(Integer, comment="买二量")
    bid3_price = Column(Float, comment="买三价")
    bid3_volume = Column(Integer, comment="买三量")
    bid4_price = Column(Float, comment="买四价")
    bid4_volume = Column(Integer, comment="买四量")
    bid5_price = Column(Float, comment="买五价")
    bid5_volume = Column(Integer, comment="买五量")

    ask1_price = Column(Float, comment="卖一价")
    ask1_volume = Column(Integer, comment="卖一量")
    ask2_price = Column(Float, comment="卖二价")
    ask2_volume = Column(Integer, comment="卖二量")
    ask3_price = Column(Float, comment="卖三价")
    ask3_volume = Column(Integer, comment="卖三量")
    ask4_price = Column(Float, comment="卖四价")
    ask4_volume = Column(Integer, comment="卖四量")
    ask5_price = Column(Float, comment="卖五价")
    ask5_volume = Column(Integer, comment="卖五量")

    # Metadata
    data_source = Column(String(20), comment="数据源")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_symbol_timestamp", "symbol", "timestamp"),
        Index("idx_quote_timestamp", "timestamp"),
    )
