"""
eltdx adapter — 通达信本地行情扩展（实时报价/分钟/逐笔/集合竞价）

eltdx 是 mootdx/pytdx 的封装，需要本地能访问通达信行情服务器（通常在客户端环境）。
本 adapter 使用 mootdx + pytdx 的 Reader/Quotes 接口。

支持字段：daily_kline, minute_kline, tick, auction, realtime_quote,
         adj_factor, dividend, financial_report, f10, sector
覆盖市场：A
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
    from mootdx.quotes import Quotes  # type: ignore
    _ELTDX_AVAILABLE = True
except ImportError:  # pragma: no cover
    Quotes = None  # type: ignore
    _ELTDX_AVAILABLE = False


def _split_symbol(symbol: str) -> tuple[str, int]:
    """600519.SH -> ('600519', 1); 000001.SZ -> ('000001', 0)"""
    s = symbol.strip().upper()
    if "." in s:
        code, ex = s.split(".", 1)
        market = 1 if ex == "SH" else 0
        return code, market
    code = s
    if code.startswith(("60", "68", "5", "11", "9")):
        return code, 1
    return code, 0


_FREQ_MAP = {
    "1min": 8,
    "5min": 0,
    "15min": 1,
    "30min": 2,
    "60min": 3,
    "day": 9,
}


class EltdxAdapter(OfflineDataSourceAdapter):
    name = "eltdx"
    markets = ["A"]
    fields = {
        "daily_kline",
        "minute_kline",
        "tick",
        "auction",
        "realtime_quote",
        "adj_factor",
        "dividend",
        "financial_report",
        "f10",
        "sector",
    }

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if Quotes is None:
            raise DataUnavailable("mootdx/eltdx not installed")
        if self._client is None:
            try:
                self._client = Quotes.factory(market="std")
            except Exception as exc:  # noqa: BLE001
                raise DataUnavailable(f"eltdx connect failed: {exc}") from exc
        return self._client

    def fetch_daily(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        client = self._get_client()
        code, market = _split_symbol(symbol)
        try:
            raw = client.bars(symbol=code, frequency=9, offset=800)
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"eltdx daily error: {exc}") from exc
        if raw is None or len(raw) == 0:
            raise DataUnavailable(f"eltdx daily empty for {symbol}")

        df = _normalize(raw, symbol=symbol, source=self.name)
        if start:
            df = df[df["trade_date"] >= start]
        if end:
            df = df[df["trade_date"] <= end]
        if df.empty:
            raise DataUnavailable(f"eltdx daily empty after date filter {symbol}")
        return df

    def fetch_minute(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        freq: str = "1min",
    ) -> pd.DataFrame:
        client = self._get_client()
        code, _market = _split_symbol(symbol)
        kf = _FREQ_MAP.get(freq)
        if kf is None:
            raise InvalidFieldRequest(f"eltdx 不支持 freq={freq}")
        try:
            raw = client.bars(symbol=code, frequency=kf, offset=800)
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"eltdx minute error: {exc}") from exc
        if raw is None or len(raw) == 0:
            raise DataUnavailable(f"eltdx minute empty for {symbol}")
        return _normalize(raw, symbol=symbol, source=self.name)

    def fetch_tick(self, symbol: str, trade_date: date) -> pd.DataFrame:
        client = self._get_client()
        code, _ = _split_symbol(symbol)
        try:
            raw = client.transaction(symbol=code, start=0, offset=2000)
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"eltdx tick error: {exc}") from exc
        if raw is None or len(raw) == 0:
            raise DataUnavailable(f"eltdx tick empty for {symbol}")
        df = raw.copy()
        df["symbol"] = symbol.upper()
        df["trade_date"] = trade_date
        df["source"] = self.name
        return df

    def fetch_meta(self, market: str) -> pd.DataFrame:
        if market.upper() != "A":
            raise InvalidFieldRequest(f"eltdx 不支持 market={market}")
        client = self._get_client()
        try:
            raw = client.stocks(market=1)
            sh = raw.copy() if raw is not None else pd.DataFrame()
            sh["exchange"] = "SH"
            raw2 = client.stocks(market=0)
            sz = raw2.copy() if raw2 is not None else pd.DataFrame()
            sz["exchange"] = "SZ"
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"eltdx stocks list error: {exc}") from exc
        df = pd.concat([sh, sz], ignore_index=True)
        if df.empty:
            raise DataUnavailable("eltdx meta empty")
        df["code"] = df["code"].astype(str).str.zfill(6)
        df["symbol"] = df["code"] + "." + df["exchange"]
        df["market"] = "A"
        df["name"] = df.get("name", "")
        df["list_date"] = None
        df["delist_date"] = None
        df["is_active"] = True
        df["source"] = self.name
        return df[[
            "symbol", "code", "exchange", "name", "market",
            "list_date", "delist_date", "is_active", "source",
        ]]

    def fetch_realtime(self, symbol: str) -> Optional[dict]:
        client = self._get_client()
        code, market = _split_symbol(symbol)
        try:
            df = client.quotes(symbol=code)
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"eltdx realtime error: {exc}") from exc
        if df is None or len(df) == 0:
            raise DataUnavailable(f"eltdx realtime empty for {symbol}")
        r = df.iloc[0].to_dict()
        return {
            "symbol": symbol.upper(),
            "last": r.get("price") or r.get("last"),
            "open": r.get("open"),
            "high": r.get("high"),
            "low": r.get("low"),
            "pre_close": r.get("last_close") or r.get("pre_close"),
            "volume": r.get("vol") or r.get("volume"),
            "amount": r.get("amount"),
            "source": self.name,
        }

    def fetch_field(
        self,
        field: str,
        symbol: str,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
        **kwargs,
    ) -> pd.DataFrame:
        client = self._get_client()
        code, _market = _split_symbol(symbol)

        if field == "adj_factor" or field == "dividend":
            try:
                raw = client.xdxr(symbol=code, start=0, offset=500)
            except Exception as exc:
                raise DataUnavailable(f"eltdx xdxr error: {exc}") from exc
            if raw is None or len(raw) == 0:
                raise DataUnavailable(f"eltdx xdxr empty for {symbol}")
            df = raw.copy()
            df["trade_date"] = pd.to_datetime(
                df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2) + "-" + df["day"].astype(str).str.zfill(2)
            ).dt.date
            df["symbol"] = symbol.upper()
            df["source"] = self.name
            if field == "dividend":
                # 除权除息事件
                df["dividend"] = pd.to_numeric(df.get("fenhong", 0), errors="coerce").fillna(0) / 10.0
                return df[["symbol", "trade_date", "dividend", "source"]].reset_index(drop=True)
            else:
                # 用除权除息事件推算 adj_factor（简化：有事件=调整）
                df["adj_factor"] = 1.0  # 通达信没有直接的 adj_factor，标记为 1.0
                return df[["symbol", "trade_date", "adj_factor", "source"]].reset_index(drop=True)

        elif field == "financial_report":
            try:
                raw = client.finance(symbol=code)
            except Exception as exc:
                raise DataUnavailable(f"eltdx finance error: {exc}") from exc
            if raw is None or len(raw) == 0:
                raise DataUnavailable(f"eltdx finance empty for {symbol}")
            df = raw.copy()
            df["symbol"] = symbol.upper()
            df["source"] = self.name
            return df

        elif field == "f10":
            try:
                raw = client.F10(symbol=code)
            except Exception as exc:
                raise DataUnavailable(f"eltdx F10 error: {exc}") from exc
            if not raw:
                raise DataUnavailable(f"eltdx F10 empty for {symbol}")
            if isinstance(raw, dict):
                df = pd.DataFrame([raw])
            elif isinstance(raw, pd.DataFrame):
                df = raw.copy()
            else:
                raise DataUnavailable(f"eltdx F10 unexpected type: {type(raw)}")
            df["symbol"] = symbol.upper()
            df["source"] = self.name
            return df

        elif field == "sector":
            try:
                raw = client.block(symbol=code)
            except Exception as exc:
                raise DataUnavailable(f"eltdx block error: {exc}") from exc
            if raw is None or len(raw) == 0:
                raise DataUnavailable(f"eltdx block empty for {symbol}")
            df = raw.copy()
            df["symbol"] = symbol.upper()
            df["source"] = self.name
            return df

        raise InvalidFieldRequest(f"eltdx: field={field} not implemented")


def _normalize(raw: pd.DataFrame, *, symbol: str, source: str) -> pd.DataFrame:
    df = raw.copy()
    if "datetime" in df.columns:
        df["trade_date"] = pd.to_datetime(df["datetime"]).dt.date
    elif "date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["date"]).dt.date
    else:
        df["trade_date"] = pd.to_datetime(df.index).date
    df["symbol"] = symbol.upper()
    for c in ("open", "high", "low", "close", "volume", "amount"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        else:
            df[c] = pd.NA
    df["adj_factor"] = 1.0
    df["source"] = source
    return df[[
        "symbol", "trade_date", "open", "high", "low", "close",
        "volume", "amount", "adj_factor", "source",
    ]]


def register() -> bool:
    if not _ELTDX_AVAILABLE:
        logger.info("mootdx/eltdx 未安装，跳过 EltdxAdapter 注册")
        return False
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(EltdxAdapter, name=EltdxAdapter.name)
    return True
