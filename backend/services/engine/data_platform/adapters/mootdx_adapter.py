"""
mootdx adapter — 通达信本地行情（mootdx 高级 Reader 模式）

eltdx 已使用 mootdx.quotes，本 adapter 走 mootdx.reader（基于本地 .day 文件）。
适合本地有通达信安装目录的场景，速度比 quotes 模式快。

支持字段：daily_kline, minute_kline
覆盖市场：A
"""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from backend.services.engine.data_platform.base import (
    DataUnavailable,
    InvalidFieldRequest,
    OfflineDataSourceAdapter,
)

logger = logging.getLogger(__name__)

try:
    from mootdx.reader import Reader  # type: ignore
    _MOOTDX_AVAILABLE = True
except ImportError:  # pragma: no cover
    Reader = None  # type: ignore
    _MOOTDX_AVAILABLE = False


def _tdx_dir() -> Optional[str]:
    return os.getenv("QM_TDX_DIR")


class MootdxAdapter(OfflineDataSourceAdapter):
    name = "mootdx"
    markets = ["A"]
    fields = {"daily_kline", "minute_kline"}

    def __init__(self) -> None:
        self._reader = None

    def _get_reader(self):
        if Reader is None:
            raise DataUnavailable("mootdx not installed")
        if self._reader is None:
            tdx = _tdx_dir()
            if not tdx or not Path(tdx).exists():
                raise DataUnavailable(
                    f"通达信目录未配置（设置 QM_TDX_DIR，当前={tdx}）"
                )
            try:
                self._reader = Reader.factory(market="std", tdxdir=tdx)
            except Exception as exc:  # noqa: BLE001
                raise DataUnavailable(f"mootdx reader factory failed: {exc}") from exc
        return self._reader

    def fetch_daily(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        reader = self._get_reader()
        code = symbol.split(".", 1)[0]
        try:
            raw = reader.daily(symbol=code)
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"mootdx daily error: {exc}") from exc
        if raw is None or len(raw) == 0:
            raise DataUnavailable(f"mootdx daily empty {symbol}")
        df = raw.reset_index().copy()
        if "datetime" in df.columns:
            df["trade_date"] = pd.to_datetime(df["datetime"]).dt.date
        elif "date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["date"]).dt.date
        else:
            df["trade_date"] = pd.to_datetime(df.iloc[:, 0]).dt.date
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
            raise DataUnavailable(f"mootdx daily empty after filter {symbol}")
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
        reader = self._get_reader()
        code = symbol.split(".", 1)[0]
        try:
            if freq == "1min":
                raw = reader.minute(symbol=code)
            elif freq == "5min":
                raw = reader.fzline(symbol=code)
            else:
                raise InvalidFieldRequest(f"mootdx 不支持 freq={freq}")
        except InvalidFieldRequest:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"mootdx minute error: {exc}") from exc
        if raw is None or len(raw) == 0:
            raise DataUnavailable(f"mootdx minute empty {symbol}")
        df = raw.reset_index().copy()
        if "datetime" in df.columns:
            df["trade_date"] = pd.to_datetime(df["datetime"]).dt.date
        df["symbol"] = symbol.upper()
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

    def fetch_meta(self, market: str) -> pd.DataFrame:
        # Reader 模式不提供完整 stocks list；交给 eltdx/baostock
        raise InvalidFieldRequest("mootdx Reader 模式不提供 meta，请用 baostock/eltdx")


def register() -> bool:
    if not _MOOTDX_AVAILABLE:
        logger.info("mootdx 未安装，跳过 MootdxAdapter 注册")
        return False
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(MootdxAdapter, name=MootdxAdapter.name)
    return True
