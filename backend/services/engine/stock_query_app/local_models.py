#!/usr/bin/env python3
"""
本地数据库股票模型
使用本地PostgreSQL数据库存储股票基础信息
"""

import os
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text, create_engine
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

_DB_URL_RAW = os.getenv("DATABASE_URL", "").strip()
if not _DB_URL_RAW:
    _DB_URL_RAW = "postgresql+psycopg2://postgres:@localhost:5432/quantmind"

DATABASE_URL = _DB_URL_RAW
SYNC_DATABASE_URL = DATABASE_URL
if SYNC_DATABASE_URL.startswith("postgresql+asyncpg://"):
    SYNC_DATABASE_URL = SYNC_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
elif SYNC_DATABASE_URL.startswith("postgresql://"):
    SYNC_DATABASE_URL = SYNC_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
engine = create_engine(SYNC_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class StockBasicInfo(Base):
    """股票基本信息模型"""

    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True, comment="股票代码")
    stock_name = Column(String(200), nullable=False, comment="股票名称")
    exchange = Column(String(20), nullable=True, index=True, comment="交易所")
    market = Column(String(20), nullable=True, index=True, comment="市场类型 (A股/港股/美股)")
    industry = Column(String(200), nullable=True, comment="行业")
    sector = Column(String(200), nullable=True, comment="板块")
    market_cap = Column(Float, nullable=True, comment="市值")
    price = Column(Float, nullable=True, comment="当前价格")
    change_pct = Column(Float, nullable=True, comment="涨跌幅")
    volume = Column(Integer, nullable=True, comment="成交量")
    total_shares = Column(Float, nullable=True, comment="总股本")
    float_shares = Column(Float, nullable=True, comment="流通股本")

    # 从 stock_realtime/财务补全 迁移过来的指标
    pe_ttm = Column(Float, nullable=True, comment="市盈率TTM")
    pb = Column(Float, nullable=True, comment="市净率")
    ps_ttm = Column(Float, nullable=True, comment="市销率TTM")
    pcf_ncf_ttm = Column(Float, nullable=True, comment="市现率TTM")
    roe = Column(Float, nullable=True, comment="净资产收益率")
    net_profit_margin = Column(Float, nullable=True, comment="净利率")
    gross_profit_margin = Column(Float, nullable=True, comment="毛利率")
    is_st = Column(Integer, default=0, comment="是否为ST股：1-是，0-否")

    turnover_rate = Column(Float, nullable=True, comment="换手率")

    status = Column(Integer, default=1, comment="状态：1-交易，0-暂停，-1-退市")

    @hybrid_property
    def is_active(self) -> bool:
        return self.status == 1

    @is_active.setter
    def is_active(self, value: bool):
        self.status = 1 if value else 0

    list_date = Column(DateTime, nullable=True, comment="上市日期")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "exchange": self.exchange,
            "industry": self.industry,
            "sector": self.sector,
            "market_cap": self.market_cap,
            "price": self.price,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "total_shares": self.total_shares,
            "float_shares": self.float_shares,
            "pe_ttm": self.pe_ttm,
            "pb": self.pb,
            "ps_ttm": self.ps_ttm,
            "pcf_ncf_ttm": self.pcf_ncf_ttm,
            "roe": self.roe,
            "net_profit_margin": self.net_profit_margin,
            "gross_profit_margin": self.gross_profit_margin,
            "is_st": bool(self.is_st),
            "turnover_rate": self.turnover_rate,
            "status": self.status,
            "list_date": self.list_date.isoformat() if self.list_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<StockBasicInfo(stock_code='{self.stock_code}', name='{self.stock_name}')>"


class StockRealTimeData(Base):
    """股票实时数据模型 (收敛至 quotes 表)平衡交易与研究需求"""

    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True, comment="股票代码")
    timestamp = Column(DateTime, nullable=False, index=True, comment="行情时间")

    # 基础行情字段
    open_price = Column(Float, nullable=True, comment="开盘价")
    high_price = Column(Float, nullable=True, comment="最高价")
    low_price = Column(Float, nullable=True, comment="最低价")
    close_price = Column(Float, nullable=True, comment="收盘价")
    current_price = Column(Float, nullable=True, comment="最新价")
    pre_close = Column(Float, nullable=True, comment="昨收价")

    # 兼容性别名 (映射 engine 服务原有字段)
    @hybrid_property
    def stock_code(self):
        return self.symbol

    @stock_code.setter
    def stock_code(self, value):
        self.symbol = value

    @hybrid_property
    def trade_date(self):
        return self.timestamp

    @trade_date.setter
    def trade_date(self, value):
        self.timestamp = value

    @hybrid_property
    def change_amount(self):
        # 如果 quotes 没存，可以计算
        return (self.current_price - self.pre_close) if self.current_price and self.pre_close else 0.0

    @hybrid_property
    def change_pct(self):
        if self.pre_close and self.pre_close != 0:
            return (self.current_price / self.pre_close - 1) * 100
        return 0.0

    volume = Column(Integer, nullable=True, comment="成交量")
    amount = Column(Float, nullable=True, comment="成交额")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    def to_dict(self):
        """转换为字典 (保持 engine 服务原有接口兼容)"""
        return {
            "id": self.id,
            "stock_code": self.stock_code,
            "trade_date": self.trade_date.isoformat() if self.trade_date else None,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "pre_close": self.pre_close,
            "change_amount": self.change_amount,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "amount": self.amount,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<StockRealTimeData(stock_code='{self.stock_code}', date='{self.trade_date}')>"


class StockIndustryInfo(Base):
    """股票行业信息模型"""

    __tablename__ = "stock_industry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True, comment="股票代码")
    industry_name = Column(String(200), nullable=True, comment="行业名称")
    industry_code = Column(String(50), nullable=True, comment="行业代码")
    sector_name = Column(String(200), nullable=True, comment="板块名称")
    sector_code = Column(String(50), nullable=True, comment="板块代码")
    concept_tags = Column(Text, nullable=True, comment="概念标签")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "stock_code": self.stock_code,
            "industry_name": self.industry_name,
            "industry_code": self.industry_code,
            "sector_name": self.sector_name,
            "sector_code": self.sector_code,
            "concept_tags": self.concept_tags.split(",") if self.concept_tags else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<StockIndustryInfo(stock_code='{self.stock_code}', industry='{self.industry_name}')>"
