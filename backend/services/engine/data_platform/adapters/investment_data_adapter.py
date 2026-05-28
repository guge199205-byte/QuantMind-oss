"""
investment_data adapter — chenditc/investment_data 离线数据集

通过环境变量 QM_INVESTMENT_DATA_DIR 指向本地目录，支持两种布局：

  布局 A — qlib bin（chenditc 官方发布的 qlib_bin.tar.gz 解压后）：
    {dir}/qlib_bin/calendars/day.txt
    {dir}/qlib_bin/features/{sz000001|sh600519|...}/{open,high,low,close,volume,amount,factor}.day.bin
    （字段名按 qlib 约定，前缀小写交易所；factor=复权因子；vwap/change 可选）

  布局 B — parquet（备用）：
    {dir}/parquet/cn_stock_daily/{600519.SH}.parquet
    或大文件 {dir}/parquet/cn_stock_daily.parquet（带 symbol 列）

支持字段：daily_kline, financial_report, dividend, adj_factor
覆盖市场：A
"""

from __future__ import annotations

import logging
import os
import struct
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backend.services.engine.data_platform.base import (
    DataUnavailable,
    InvalidFieldRequest,
    OfflineDataSourceAdapter,
)

logger = logging.getLogger(__name__)

DATA_DIR_ENV = "QM_INVESTMENT_DATA_DIR"

# qlib 字段 → 标准列名（取标准 OHLCV + amount + factor）
_QLIB_FIELD_MAP = {
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "amount": "amount",
    "factor": "adj_factor",
}


def _data_dir() -> Optional[Path]:
    raw = os.getenv(DATA_DIR_ENV, "").strip()
    if not raw:
        return None
    p = Path(raw)
    return p if p.exists() else None


def _to_qlib_symbol(symbol: str) -> str:
    """600519.SH → sh600519 / 000001.SZ → sz000001"""
    s = symbol.upper().strip()
    if "." in s:
        code, ex = s.split(".", 1)
        return f"{ex.lower()}{code}"
    if len(s) >= 8 and s[:2] in ("SH", "SZ", "BJ"):
        return s.lower()
    return s.lower()


def _qlib_root(root: Path) -> Optional[Path]:
    """返回 qlib_bin 目录，没有就 None。"""
    for cand in (root / "qlib_bin", root / "qlib" / "qlib_cn", root):
        if (cand / "calendars" / "day.txt").exists() and (cand / "features").exists():
            return cand
    return None


@lru_cache(maxsize=4)
def _load_calendar(qroot_str: str) -> np.ndarray:
    """加载 day.txt 为 np.datetime64[D] array（按行号即 qlib 索引）。"""
    qroot = Path(qroot_str)
    cal_file = qroot / "calendars" / "day.txt"
    with cal_file.open("r", encoding="utf-8") as f:
        rows = [line.strip() for line in f if line.strip()]
    return np.array(rows, dtype="datetime64[D]")


def _read_qlib_bin(path: Path) -> tuple[int, np.ndarray]:
    """
    读取 qlib .day.bin：4 字节 header（float32 起始索引）+ N 个 float32 值。
    返回 (start_index, values_array)。
    """
    raw = path.read_bytes()
    if len(raw) < 4:
        raise DataUnavailable(f"{path} too small")
    start_idx = int(struct.unpack("<f", raw[:4])[0])
    n = (len(raw) - 4) // 4
    values = np.frombuffer(raw, dtype=np.float32, count=n, offset=4)
    return start_idx, values


class InvestmentDataAdapter(OfflineDataSourceAdapter):
    name = "investment_data"
    markets = ["A"]
    fields = {"daily_kline", "financial_report", "dividend", "adj_factor"}

    def __init__(self) -> None:
        self.root = _data_dir()
        if self.root is None:
            logger.info(
                "%s=未设置或目录不存在，InvestmentDataAdapter 将仅在请求时报错",
                DATA_DIR_ENV,
            )

    def _require_root(self) -> Path:
        if self.root is None or not self.root.exists():
            raise DataUnavailable(
                f"investment_data 目录未配置（设置 {DATA_DIR_ENV} 指向 chenditc/investment_data 克隆路径）"
            )
        return self.root

    # ------------------------------------------------------------------
    # qlib bin 读取
    # ------------------------------------------------------------------
    def _fetch_daily_qlib_bin(
        self, qroot: Path, symbol: str, start: Optional[date], end: Optional[date],
    ) -> Optional[pd.DataFrame]:
        qsym = _to_qlib_symbol(symbol)
        sym_dir = qroot / "features" / qsym
        if not sym_dir.exists():
            return None

        calendar = _load_calendar(str(qroot))
        cal_len = len(calendar)

        series: dict[str, np.ndarray] = {}
        for qf, std in _QLIB_FIELD_MAP.items():
            f = sym_dir / f"{qf}.day.bin"
            if not f.exists():
                continue
            try:
                start_idx, vals = _read_qlib_bin(f)
            except Exception as exc:
                logger.warning("read %s failed: %s", f, exc)
                continue
            # 对齐到 calendar：[start_idx, start_idx+len(vals))
            full = np.full(cal_len, np.nan, dtype=np.float64)
            end_idx = min(start_idx + len(vals), cal_len)
            full[start_idx:end_idx] = vals[: end_idx - start_idx]
            series[std] = full

        if "close" not in series:
            return None  # 没有 close，认为该 symbol 无数据

        df = pd.DataFrame(series)
        df["trade_date"] = pd.to_datetime(calendar).date
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        if df.empty:
            return None

        if start:
            df = df[df["trade_date"] >= start]
        if end:
            df = df[df["trade_date"] <= end]
        if df.empty:
            return None

        df["symbol"] = symbol.upper()
        for c in ("open", "high", "low", "close", "volume", "amount", "adj_factor"):
            if c not in df.columns:
                df[c] = pd.NA
        df["adj_factor"] = df["adj_factor"].fillna(1.0)
        df["source"] = self.name
        return df[[
            "symbol", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "adj_factor", "source",
        ]].reset_index(drop=True)

    # ------------------------------------------------------------------
    def fetch_daily(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        root = self._require_root()

        # 1) 优先尝试 qlib bin（chenditc 官方发布格式）
        qroot = _qlib_root(root)
        if qroot is not None:
            df = self._fetch_daily_qlib_bin(qroot, symbol, start, end)
            if df is not None and not df.empty:
                return df

        # 2) 回退到 parquet 布局
        f = root / "parquet" / "cn_stock_daily" / f"{symbol.upper()}.parquet"
        if f.exists():
            df = pd.read_parquet(f)
        else:
            big = root / "parquet" / "cn_stock_daily.parquet"
            if big.exists():
                df = pd.read_parquet(big, filters=[("symbol", "==", symbol.upper())])
            else:
                raise DataUnavailable(
                    f"investment_data 无 {symbol} 数据（qlib_bin 与 parquet 均未命中）"
                )

        if df is None or df.empty:
            raise DataUnavailable(f"investment_data {symbol} parquet empty")

        df = df.copy()
        if "trade_date" not in df.columns and "date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["date"]).dt.date
        elif "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        if start:
            df = df[df["trade_date"] >= start]
        if end:
            df = df[df["trade_date"] <= end]
        if df.empty:
            raise DataUnavailable(f"investment_data empty after date filter {symbol}")

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
            raise InvalidFieldRequest(f"investment_data 不支持 market={market}")
        f = root / "parquet" / "cn_stock_meta.parquet"
        if not f.exists():
            raise DataUnavailable(f"investment_data 缺少 {f}")
        df = pd.read_parquet(f).copy()
        if "symbol" not in df.columns:
            raise DataUnavailable("investment_data meta 缺少 symbol 列")
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
        if field == "adj_factor":
            return self._fetch_adj(root, symbol, start, end)
        if field == "financial_report":
            return self._fetch_fin(root, symbol)
        if field == "dividend":
            return self._fetch_div(root, symbol)
        raise InvalidFieldRequest(f"investment_data: field={field} not implemented")

    def _fetch_adj(self, root: Path, symbol: str, start, end) -> pd.DataFrame:
        f = root / "parquet" / "cn_stock_adj" / f"{symbol.upper()}.parquet"
        if not f.exists():
            raise DataUnavailable(f"{f} not found")
        df = pd.read_parquet(f).copy()
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df

    def _fetch_fin(self, root: Path, symbol: str) -> pd.DataFrame:
        f = root / "parquet" / "cn_stock_financial" / f"{symbol.upper()}.parquet"
        if not f.exists():
            raise DataUnavailable(f"{f} not found")
        df = pd.read_parquet(f).copy()
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df

    def _fetch_div(self, root: Path, symbol: str) -> pd.DataFrame:
        f = root / "parquet" / "cn_stock_dividend" / f"{symbol.upper()}.parquet"
        if not f.exists():
            raise DataUnavailable(f"{f} not found")
        df = pd.read_parquet(f).copy()
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df


def register() -> bool:
    """无需第三方库；总是可注册（运行时才检查目录）。"""
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(InvestmentDataAdapter, name=InvestmentDataAdapter.name)
    return True
