"""
标准化数据模型与列定义。

各适配器返回的 DataFrame 必须遵循这里定义的列名（多余列允许保留）。
聚合层会按这些列做对齐、去重、共识投票。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


# ---------------------------------------------------------------------------
# 标准列定义（与 Qlib / Parquet 写出顺序一致）
# ---------------------------------------------------------------------------
OHLCV_COLUMNS: list[str] = [
    "symbol",       # 标准符号 600519.SH / 00700.HK / AAPL.US
    "trade_date",   # date / pd.Timestamp(date)
    "open",
    "high",
    "low",
    "close",
    "volume",       # 成交量（股）
    "amount",       # 成交额（元 / 港元 / 美元）
    "adj_factor",   # 复权因子（前复权基准 1.0）
    "source",       # 数据源名 (baostock / efinance / ...)
]

FUNDAMENTAL_COLUMNS: list[str] = [
    "symbol",
    "report_date",
    "ann_date",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "total_mv",     # 总市值（元）
    "float_mv",     # 流通市值（元）
    "roe",
    "roa",
    "eps",
    "bps",
    "revenue",
    "net_profit",
    "source",
]

SYMBOL_META_COLUMNS: list[str] = [
    "symbol",
    "code",
    "exchange",
    "name",
    "market",       # A / HK / US
    "list_date",
    "delist_date",
    "is_active",
    "sector",
    "industry",
    "source",
]


# ---------------------------------------------------------------------------
# 数据类（适配器内部可选使用，DataFrame 仍是首选）
# ---------------------------------------------------------------------------
@dataclass
class OHLCVRow:
    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    adj_factor: float = 1.0
    source: str = ""


@dataclass
class FundamentalRow:
    symbol: str
    report_date: date
    ann_date: Optional[date] = None
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    ps_ttm: Optional[float] = None
    total_mv: Optional[float] = None
    float_mv: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    eps: Optional[float] = None
    bps: Optional[float] = None
    revenue: Optional[float] = None
    net_profit: Optional[float] = None
    source: str = ""


@dataclass
class SymbolMeta:
    symbol: str
    code: str
    exchange: str
    name: str
    market: str
    list_date: Optional[date] = None
    delist_date: Optional[date] = None
    is_active: bool = True
    sector: str = ""
    industry: str = ""
    source: str = ""


@dataclass
class RealtimeQuote:
    symbol: str
    ts: datetime
    last: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    pre_close: Optional[float] = None
    bid_price: list[float] = field(default_factory=list)
    bid_volume: list[float] = field(default_factory=list)
    ask_price: list[float] = field(default_factory=list)
    ask_volume: list[float] = field(default_factory=list)
    volume: Optional[float] = None
    amount: Optional[float] = None
    source: str = ""
