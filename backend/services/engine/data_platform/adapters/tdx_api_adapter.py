"""
tdx_api adapter — oficcejo/tdx-api（HTTP REST 封装通达信行情）

设定一个本地服务地址（默认 http://localhost:7708），通过 requests 访问。

支持字段：daily_kline, minute_kline, tick, auction, realtime_quote
覆盖市场：A
"""

from __future__ import annotations

import logging
import os
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
    import requests  # type: ignore
    _REQ_AVAILABLE = True
except ImportError:  # pragma: no cover
    requests = None  # type: ignore
    _REQ_AVAILABLE = False


def _base_url() -> str:
    return os.getenv("QM_TDX_API_URL", "http://localhost:7708").rstrip("/")


def _to_market_code(symbol: str) -> tuple[int, str]:
    s = symbol.strip().upper()
    if "." in s:
        code, ex = s.split(".", 1)
        return (1 if ex == "SH" else 0), code
    if s.startswith(("60", "68", "9", "11", "5")):
        return 1, s
    return 0, s


class TdxApiAdapter(OfflineDataSourceAdapter):
    name = "tdx_api"
    markets = ["A"]
    fields = {
        "daily_kline",
        "minute_kline",
        "tick",
        "auction",
        "realtime_quote",
    }

    def __init__(self) -> None:
        self.base = _base_url()
        if not _REQ_AVAILABLE:
            logger.warning("requests 库缺失，tdx_api 不可用")

    def _get(self, path: str, params: dict) -> dict:
        if not _REQ_AVAILABLE:
            raise DataUnavailable("requests not installed")
        url = f"{self.base}{path}"
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"tdx_api GET {url} failed: {exc}") from exc
        try:
            return r.json()
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"tdx_api 非 JSON 响应: {exc}") from exc

    def fetch_daily(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        market, code = _to_market_code(symbol)
        data = self._get("/api/k", {
            "market": market, "code": code, "category": 9, "count": 800,
        })
        rows = data.get("data") if isinstance(data, dict) else None
        if not rows:
            raise DataUnavailable(f"tdx_api daily empty {symbol}")
        df = pd.DataFrame(rows)
        if "datetime" in df.columns:
            df["trade_date"] = pd.to_datetime(df["datetime"]).dt.date
        elif "date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["date"]).dt.date
        df["symbol"] = symbol.upper()
        for c in ("open", "high", "low", "close", "vol", "amount"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "vol" in df.columns and "volume" not in df.columns:
            df["volume"] = df["vol"]
        df["adj_factor"] = 1.0
        df["source"] = self.name
        if start:
            df = df[df["trade_date"] >= start]
        if end:
            df = df[df["trade_date"] <= end]
        if df.empty:
            raise DataUnavailable(f"tdx_api daily empty after filter {symbol}")
        return df[[
            "symbol", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "adj_factor", "source",
        ]]

    def fetch_minute(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        freq: str = "1min",
    ) -> pd.DataFrame:
        market, code = _to_market_code(symbol)
        cat = {"1min": 8, "5min": 0, "15min": 1, "30min": 2, "60min": 3}.get(freq)
        if cat is None:
            raise InvalidFieldRequest(f"tdx_api 不支持 freq={freq}")
        data = self._get("/api/k", {
            "market": market, "code": code, "category": cat, "count": 800,
        })
        rows = data.get("data") if isinstance(data, dict) else None
        if not rows:
            raise DataUnavailable(f"tdx_api minute empty {symbol}")
        df = pd.DataFrame(rows)
        df["symbol"] = symbol.upper()
        df["trade_date"] = pd.to_datetime(df.get("datetime")).dt.date
        for c in ("open", "high", "low", "close", "vol", "amount"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "vol" in df.columns and "volume" not in df.columns:
            df["volume"] = df["vol"]
        df["adj_factor"] = 1.0
        df["source"] = self.name
        return df[[
            "symbol", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "adj_factor", "source",
        ]]

    def fetch_realtime(self, symbol: str) -> Optional[dict]:
        market, code = _to_market_code(symbol)
        data = self._get("/api/quote", {"market": market, "code": code})
        rows = data.get("data") if isinstance(data, dict) else None
        if not rows:
            raise DataUnavailable(f"tdx_api realtime empty {symbol}")
        r = rows[0] if isinstance(rows, list) else rows
        return {
            "symbol": symbol.upper(),
            "last": r.get("price"),
            "open": r.get("open"),
            "high": r.get("high"),
            "low": r.get("low"),
            "pre_close": r.get("last_close"),
            "volume": r.get("vol"),
            "amount": r.get("amount"),
            "source": self.name,
        }

    def fetch_meta(self, market: str) -> pd.DataFrame:
        if market.upper() != "A":
            raise InvalidFieldRequest(f"tdx_api 不支持 market={market}")
        data = self._get("/api/stocks", {"market": 1})
        sh_rows = data.get("data", []) if isinstance(data, dict) else []
        data2 = self._get("/api/stocks", {"market": 0})
        sz_rows = data2.get("data", []) if isinstance(data2, dict) else []
        all_rows = []
        for ex, rows in (("SH", sh_rows), ("SZ", sz_rows)):
            for r in rows:
                code = str(r.get("code") or "").zfill(6)
                all_rows.append({
                    "symbol": f"{code}.{ex}",
                    "code": code,
                    "exchange": ex,
                    "name": r.get("name", ""),
                    "market": "A",
                    "list_date": None,
                    "delist_date": None,
                    "is_active": True,
                    "source": self.name,
                })
        if not all_rows:
            raise DataUnavailable("tdx_api meta empty")
        return pd.DataFrame(all_rows)

    def fetch_tick(self, symbol: str, trade_date: date) -> pd.DataFrame:
        market, code = _to_market_code(symbol)
        data = self._get("/api/transaction", {"market": market, "code": code, "count": 2000})
        rows = data.get("data") if isinstance(data, dict) else None
        if not rows:
            raise DataUnavailable(f"tdx_api tick empty {symbol}")
        df = pd.DataFrame(rows)
        df["symbol"] = symbol.upper()
        df["trade_date"] = trade_date
        df["source"] = self.name
        return df


def register() -> bool:
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(TdxApiAdapter, name=TdxApiAdapter.name)
    return True
