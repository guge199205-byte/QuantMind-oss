"""
simonlin_global adapter — 港股/美股离线 parquet 数据

类似 simonlin_a_stock，通过 QM_SIMONLIN_GLOBAL_DIR 环境变量指向数据目录。
目录结构：
  daily/  → {SYMBOL}.parquet  (如 0700.HK.parquet, AAPL.parquet)
  meta.parquet
  financial/ → {SYMBOL}.parquet (可选)
  dividend/  → {SYMBOL}.parquet (可选)

支持字段：daily_kline, financial_report, dividend
覆盖市场：HK, US
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

DATA_DIR_ENV = "QM_SIMONLIN_GLOBAL_DIR"


def _data_dir() -> Optional[Path]:
    raw = os.getenv(DATA_DIR_ENV, "").strip()
    if not raw:
        return None
    p = Path(raw)
    return p if p.exists() else None


def _norm_symbol(symbol: str) -> str:
    """Normalize symbol for file lookup: 00700.HK -> 0700.HK, AAPL -> AAPL."""
    s = symbol.strip().upper()
    if s.endswith(".HK"):
        code = s.split(".")[0]
        return f"{int(code)}.HK"
    return s


class SimonLinGlobalAdapter(OfflineDataSourceAdapter):
    name = "simonlin_global"
    markets = ["HK", "US"]
    fields = {"daily_kline", "financial_report", "dividend"}

    def __init__(self) -> None:
        self.root = _data_dir()

    def _require_root(self) -> Path:
        if self.root is None or not self.root.exists():
            raise DataUnavailable(
                f"simonlin_global 目录未配置（设置 {DATA_DIR_ENV} 指向数据路径）"
            )
        return self.root

    def fetch_daily(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        root = self._require_root()
        norm = _norm_symbol(symbol)
        f = root / "daily" / f"{norm}.parquet"
        if not f.exists():
            raise DataUnavailable(f"simonlin_global {f} not found")
        df = pd.read_parquet(f).copy()
        if "trade_date" not in df.columns and "date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["date"]).dt.date
        elif "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        if start:
            df = df[df["trade_date"] >= start]
        if end:
            df = df[df["trade_date"] <= end]
        if df.empty:
            raise DataUnavailable(f"simonlin_global {symbol} empty after filter")
        df["symbol"] = symbol.upper()
        for c in ("open", "high", "low", "close", "volume", "amount", "adj_factor"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            else:
                df[c] = pd.NA
        df["adj_factor"] = df["adj_factor"].fillna(1.0)
        df["source"] = self.name
        return df[[
            "symbol", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "adj_factor", "source",
        ]]

    def fetch_meta(self, market: str) -> pd.DataFrame:
        root = self._require_root()
        m = market.upper()
        if m not in ("HK", "US"):
            raise InvalidFieldRequest(f"simonlin_global 不支持 market={market}")
        f = root / "meta.parquet"
        if not f.exists():
            raise DataUnavailable(f"simonlin_global meta 缺少 {f}")
        df = pd.read_parquet(f).copy()
        if "market" in df.columns:
            df = df[df["market"].str.upper() == m]
        df["source"] = self.name
        return df

    def fetch_field(
        self,
        field: str,
        symbol: str,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
        **kwargs,
    ) -> pd.DataFrame:
        root = self._require_root()
        norm = _norm_symbol(symbol)
        if field == "financial_report":
            f = root / "financial" / f"{norm}.parquet"
        elif field == "dividend":
            f = root / "dividend" / f"{norm}.parquet"
        else:
            raise InvalidFieldRequest(f"simonlin_global: field={field}")
        if not f.exists():
            raise DataUnavailable(f"{f} not found")
        df = pd.read_parquet(f).copy()
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df


def register() -> bool:
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(SimonLinGlobalAdapter, name=SimonLinGlobalAdapter.name)
    return True
