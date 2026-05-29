"""
injoyai_tdx adapter — injoyai/tdx 项目（Python 封装通达信本地协议，提供 OHLCV 简洁接口）

由于 injoyai_tdx 在线版本不一定可访问，本 adapter 走 module 路径
    injoyai_tdx.api.Tdx
当模块不可用时 register() 静默跳过。

支持字段：daily_kline, minute_kline, realtime_quote
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
    import injoyai_tdx  # type: ignore
    _INJOY_AVAILABLE = True
except ImportError:  # pragma: no cover
    injoyai_tdx = None  # type: ignore
    _INJOY_AVAILABLE = False


class InjoyaiTdxAdapter(OfflineDataSourceAdapter):
    name = "injoyai_tdx"
    markets = ["A"]
    fields = {"daily_kline", "minute_kline", "realtime_quote"}

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if injoyai_tdx is None:
            raise DataUnavailable("injoyai_tdx not installed")
        if self._client is None:
            try:
                from injoyai_tdx.api import Tdx  # type: ignore
                self._client = Tdx()
            except Exception as exc:  # noqa: BLE001
                raise DataUnavailable(f"injoyai_tdx init failed: {exc}") from exc
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
        code = symbol.split(".", 1)[0]
        try:
            raw = client.daily(code=code, count=800)
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"injoyai_tdx daily error: {exc}") from exc
        if raw is None or len(raw) == 0:
            raise DataUnavailable(f"injoyai_tdx daily empty {symbol}")
        df = pd.DataFrame(raw) if not isinstance(raw, pd.DataFrame) else raw.copy()
        if "date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["date"]).dt.date
        elif "datetime" in df.columns:
            df["trade_date"] = pd.to_datetime(df["datetime"]).dt.date
        df["symbol"] = symbol.upper()
        for c in ("open", "high", "low", "close", "volume", "amount"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            else:
                df[c] = pd.NA
        df["adj_factor"] = 1.0
        df["source"] = self.name
        if start:
            df = df[df["trade_date"] >= start]
        if end:
            df = df[df["trade_date"] <= end]
        if df.empty:
            raise DataUnavailable(f"injoyai_tdx daily empty after filter {symbol}")
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
        client = self._get_client()
        code = symbol.split(".", 1)[0]
        if freq != "1min":
            raise InvalidFieldRequest(f"injoyai_tdx 当前仅支持 1min")
        try:
            raw = client.minute(code=code, count=240)
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"injoyai_tdx minute error: {exc}") from exc
        if raw is None or len(raw) == 0:
            raise DataUnavailable(f"injoyai_tdx minute empty {symbol}")
        df = pd.DataFrame(raw) if not isinstance(raw, pd.DataFrame) else raw.copy()
        df["symbol"] = symbol.upper()
        df["trade_date"] = pd.to_datetime(df.get("datetime")).dt.date
        for c in ("open", "high", "low", "close", "volume", "amount"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            else:
                df[c] = pd.NA
        df["adj_factor"] = 1.0
        df["source"] = self.name
        return df[[
            "symbol", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "adj_factor", "source",
        ]]

    def fetch_realtime(self, symbol: str) -> Optional[dict]:
        client = self._get_client()
        code = symbol.split(".", 1)[0]
        try:
            r = client.quote(code=code)
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"injoyai_tdx realtime error: {exc}") from exc
        if not r:
            raise DataUnavailable(f"injoyai_tdx realtime empty {symbol}")
        r = r if isinstance(r, dict) else {}
        return {
            "symbol": symbol.upper(),
            "last": r.get("price"),
            "open": r.get("open"),
            "high": r.get("high"),
            "low": r.get("low"),
            "pre_close": r.get("last_close"),
            "volume": r.get("volume"),
            "amount": r.get("amount"),
            "source": self.name,
        }

    def fetch_meta(self, market: str) -> pd.DataFrame:
        raise InvalidFieldRequest("injoyai_tdx 不提供 meta，请用 baostock/akshare")


def register() -> bool:
    if not _INJOY_AVAILABLE:
        logger.info("injoyai_tdx 未安装，跳过 InjoyaiTdxAdapter 注册")
        return False
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(InjoyaiTdxAdapter, name=InjoyaiTdxAdapter.name)
    return True
