"""
efinance adapter — 东方财富数据接口（A/HK/US 通用）

支持字段：daily_kline, minute_kline, realtime_quote, money_flow, dragon_tiger,
          block_trade, share_unlock, dividend
覆盖市场：A, HK, US

efinance 是同步 requests 库；速率较低，需要 retry。
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import pandas as pd

from backend.services.engine.data_platform.base import (
    DataUnavailable,
    InvalidFieldRequest,
    OfflineDataSourceAdapter,
)

logger = logging.getLogger(__name__)

try:
    import efinance as ef  # type: ignore
    _EF_AVAILABLE = True
except ImportError:  # pragma: no cover
    ef = None  # type: ignore
    _EF_AVAILABLE = False


def _to_ef_code(symbol: str, market: str) -> str:
    """efinance 用纯数字代码或带后缀：A 用 000001；HK 用 00700；US 用 AAPL。"""
    s = symbol.strip().upper()
    if "." in s:
        code, _ex = s.split(".", 1)
        return code
    return s


_KLINE_KLT = {"1min": 1, "5min": 5, "15min": 15, "30min": 30, "60min": 60, "day": 101}
_FQT = {"none": 0, "qfq": 1, "hfq": 2}


class EfinanceAdapter(OfflineDataSourceAdapter):
    name = "efinance"
    markets = ["A", "HK", "US"]
    fields = {
        "daily_kline",
        "minute_kline",
        "realtime_quote",
        "money_flow",
        "dragon_tiger",
        "block_trade",
        "share_unlock",
        "dividend",
        "adj_factor",
    }

    def fetch_daily(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        if ef is None:
            raise DataUnavailable("efinance not installed")
        code = _to_ef_code(symbol, market="A")
        fqt = _FQT.get(adjust, 1)
        try:
            raw = ef.stock.get_quote_history(
                code,
                beg=start.strftime("%Y%m%d") if start else "20000101",
                end=end.strftime("%Y%m%d") if end else "20991231",
                klt=101, fqt=fqt,
            )
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"efinance get_quote_history error: {exc}") from exc
        if raw is None or raw.empty:
            raise DataUnavailable(f"efinance empty for {symbol}")
        return _normalize_kline(raw, symbol=symbol, source=self.name)

    def fetch_minute(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        freq: str = "1min",
    ) -> pd.DataFrame:
        if ef is None:
            raise DataUnavailable("efinance not installed")
        klt = _KLINE_KLT.get(freq)
        if klt is None:
            raise InvalidFieldRequest(f"efinance 不支持 freq={freq}")
        try:
            raw = ef.stock.get_quote_history(
                _to_ef_code(symbol, "A"),
                beg=start.strftime("%Y%m%d") if start else "20000101",
                end=end.strftime("%Y%m%d") if end else "20991231",
                klt=klt, fqt=1,
            )
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"efinance minute error: {exc}") from exc
        if raw is None or raw.empty:
            raise DataUnavailable(f"efinance minute empty for {symbol} {freq}")
        return _normalize_kline(raw, symbol=symbol, source=self.name)

    def fetch_meta(self, market: str) -> pd.DataFrame:
        if ef is None:
            raise DataUnavailable("efinance not installed")
        m = market.upper()
        if m == "A":
            getter = ef.stock.get_realtime_quotes
            args = []
        elif m == "HK":
            getter = ef.stock.get_realtime_quotes
            args = ["港股"]
        elif m == "US":
            getter = ef.stock.get_realtime_quotes
            args = ["美股"]
        else:
            raise InvalidFieldRequest(f"efinance 不支持 market={market}")
        try:
            raw = getter(*args)
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"efinance meta error: {exc}") from exc
        if raw is None or raw.empty:
            raise DataUnavailable(f"efinance meta empty for {market}")
        df = raw.rename(columns={
            "股票代码": "code", "股票名称": "name",
        }).copy()
        if "code" not in df.columns:
            raise DataUnavailable("efinance meta missing code column")
        df["symbol"] = df["code"].astype(str).str.upper().apply(
            lambda c: f"{c}.{_guess_exchange(c, m)}" if "." not in c else c
        )
        df["exchange"] = df["symbol"].str.split(".").str[1]
        df["market"] = m
        df["is_active"] = True
        df["list_date"] = None
        df["delist_date"] = None
        df["source"] = self.name
        return df[[
            "symbol", "code", "exchange", "name", "market",
            "list_date", "delist_date", "is_active", "source",
        ]]

    def fetch_realtime(self, symbol: str) -> Optional[dict]:
        if ef is None:
            raise DataUnavailable("efinance not installed")
        try:
            df = ef.stock.get_latest_quote([_to_ef_code(symbol, "A")])
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"efinance realtime error: {exc}") from exc
        if df is None or df.empty:
            raise DataUnavailable(f"efinance realtime empty for {symbol}")
        row = df.iloc[0].to_dict()
        return {
            "symbol": symbol.upper(),
            "last": row.get("最新价"),
            "open": row.get("今开"),
            "high": row.get("最高"),
            "low": row.get("最低"),
            "pre_close": row.get("昨收"),
            "volume": row.get("成交量"),
            "amount": row.get("成交额"),
            "source": self.name,
        }


def _guess_exchange(code: str, market: str) -> str:
    if market != "A":
        return market
    if code.startswith(("60", "68", "11", "51", "5")):
        return "SH"
    if code.startswith(("00", "30", "12", "15", "16")):
        return "SZ"
    if code.startswith(("4", "8", "9")):
        return "BJ"
    return "SH"


def _normalize_kline(raw: pd.DataFrame, *, symbol: str, source: str) -> pd.DataFrame:
    """efinance 列名为中文，统一映射。"""
    rename = {
        "日期": "trade_date",
        "时间": "trade_date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
    }
    df = raw.rename(columns=rename).copy()
    df["symbol"] = symbol.upper()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    for c in ("open", "high", "low", "close", "volume", "amount"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["adj_factor"] = 1.0
    df["source"] = source
    return df[[
        "symbol", "trade_date", "open", "high", "low", "close",
        "volume", "amount", "adj_factor", "source",
    ]]


def register() -> bool:
    if not _EF_AVAILABLE:
        logger.info("efinance 未安装，跳过 EfinanceAdapter 注册")
        return False
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(EfinanceAdapter, name=EfinanceAdapter.name)
    return True
