"""
simonlin_a_stock adapter — simonlin1212/a-stock-data 离线 parquet 集合

类似 investment_data，是 GitHub 上的 A 股开源数据仓库。
通过 QM_SIMONLIN_A_DIR 环境变量指向克隆目录。

支持字段：daily_kline, financial_report, f10
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

DATA_DIR_ENV = "QM_SIMONLIN_A_DIR"


def _data_dir() -> Optional[Path]:
    raw = os.getenv(DATA_DIR_ENV, "").strip()
    if not raw:
        return None
    p = Path(raw)
    return p if p.exists() else None


class SimonLinAStockAdapter(OfflineDataSourceAdapter):
    name = "simonlin_a_stock"
    markets = ["A"]
    fields = {"daily_kline", "financial_report", "f10"}

    def __init__(self) -> None:
        self.root = _data_dir()

    def _require_root(self) -> Path:
        if self.root is None or not self.root.exists():
            raise DataUnavailable(
                f"simonlin_a_stock 目录未配置（设置 {DATA_DIR_ENV} 指向克隆路径）"
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
        f = root / "daily" / f"{symbol.upper()}.parquet"
        if not f.exists():
            raise DataUnavailable(f"simonlin_a_stock {f} not found")
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
            raise DataUnavailable(f"simonlin_a_stock {symbol} empty after filter")
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
        if market.upper() != "A":
            raise InvalidFieldRequest(f"simonlin_a_stock 不支持 market={market}")
        f = root / "meta.parquet"
        if not f.exists():
            raise DataUnavailable(f"simonlin_a_stock meta 缺少 {f}")
        df = pd.read_parquet(f).copy()
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
        if field == "financial_report":
            f = root / "financial" / f"{symbol.upper()}.parquet"
        elif field == "f10":
            f = root / "f10" / f"{symbol.upper()}.parquet"
        else:
            raise InvalidFieldRequest(f"simonlin_a_stock: field={field}")
        if not f.exists():
            raise DataUnavailable(f"{f} not found")
        df = pd.read_parquet(f).copy()
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df


def register() -> bool:
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(SimonLinAStockAdapter, name=SimonLinAStockAdapter.name)
    return True
