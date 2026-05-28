"""
DataCleaner: 4 层清洗。

L1 Schema       — 必备列、类型、缺失列填充
L2 Range        — 价格 > 0、量 >= 0、open/high/low/close 关系
L3 Outlier      — 单日涨跌幅 / Z-score 异常剔除或标记
L4 Consensus    — 与基准的偏离记录（由 FieldAggregator 在共识模式下传入）

清洗目标：
- 不静默吞掉数据，所有删除/标记都进 report
- 默认非破坏：标记 invalid 列；仅在 strict=True 时丢弃
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


REQUIRED_OHLCV = ("symbol", "trade_date", "open", "high", "low", "close", "volume")

# 各市场单日涨跌幅上限（绝对值）。超过视为异常。
MAX_DAILY_CHANGE = {
    "A": 0.22,    # ST/科创板理论 20%，留 2% 余量
    "HK": 0.50,
    "US": 1.00,
}


@dataclass
class CleaningReport:
    rows_in: int = 0
    rows_out: int = 0
    schema_filled: dict[str, int] = field(default_factory=dict)
    range_violations: int = 0
    outliers_marked: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "schema_filled": dict(self.schema_filled),
            "range_violations": self.range_violations,
            "outliers_marked": self.outliers_marked,
            "notes": list(self.notes),
        }


class DataCleaner:
    def __init__(self, *, strict: bool = False) -> None:
        self.strict = strict

    def clean(
        self,
        df: pd.DataFrame,
        *,
        market: str,
        field: str,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        report = CleaningReport(rows_in=len(df))

        if df is None or df.empty:
            report.notes.append("input empty")
            return df, report.as_dict()

        if field in ("daily_kline", "minute_kline"):
            df = self._l1_schema_ohlcv(df, report)
            df = self._l2_range_ohlcv(df, report)
            df = self._l3_outlier_ohlcv(df, market=market, report=report)
        elif field == "adj_factor":
            df = self._l1_schema_required(df, ("symbol", "trade_date", "adj_factor"), report)
            df = self._l2_adj_factor(df, report)
        elif field == "financial_report":
            df = self._l1_schema_required(df, ("symbol", "report_date"), report)
        # 其他字段：仅做空值检查
        else:
            df = self._l1_schema_required(df, ("symbol",), report)

        report.rows_out = len(df)
        return df, report.as_dict()

    # ---- L1 ----
    def _l1_schema_ohlcv(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        df = df.copy()
        for col in REQUIRED_OHLCV:
            if col not in df.columns:
                df[col] = pd.NA
                report.schema_filled[col] = len(df)
                report.notes.append(f"L1: filled missing column {col}")
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.date
        for c in ("open", "high", "low", "close", "volume", "amount", "adj_factor"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        before = len(df)
        df = df.dropna(subset=["symbol", "trade_date", "close"]).reset_index(drop=True)
        dropped = before - len(df)
        if dropped:
            report.notes.append(f"L1: dropped {dropped} rows missing symbol/date/close")
        return df

    def _l1_schema_required(
        self,
        df: pd.DataFrame,
        required: tuple[str, ...],
        report: CleaningReport,
    ) -> pd.DataFrame:
        df = df.copy()
        for col in required:
            if col not in df.columns:
                df[col] = pd.NA
                report.schema_filled[col] = len(df)
        before = len(df)
        df = df.dropna(subset=list(required)).reset_index(drop=True)
        dropped = before - len(df)
        if dropped:
            report.notes.append(f"L1: dropped {dropped} rows missing required {required}")
        return df

    # ---- L2 ----
    def _l2_range_ohlcv(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        df = df.copy()
        # 价格必须 > 0
        price_cols = ["open", "high", "low", "close"]
        bad_price_mask = (df[price_cols] <= 0).any(axis=1)
        # high >= max(open, close, low), low <= min(...)
        bad_rel_mask = (
            (df["high"] < df[["open", "close", "low"]].max(axis=1)) |
            (df["low"] > df[["open", "close", "high"]].min(axis=1))
        )
        bad_volume_mask = df["volume"] < 0

        violations = int((bad_price_mask | bad_rel_mask | bad_volume_mask).sum())
        report.range_violations = violations

        if violations:
            report.notes.append(f"L2: {violations} range violations")
            if self.strict:
                df = df.loc[~(bad_price_mask | bad_rel_mask | bad_volume_mask)].reset_index(drop=True)
            else:
                if "invalid_range" not in df.columns:
                    df["invalid_range"] = False
                df.loc[bad_price_mask | bad_rel_mask | bad_volume_mask, "invalid_range"] = True
        return df

    def _l2_adj_factor(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        df = df.copy()
        df["adj_factor"] = pd.to_numeric(df["adj_factor"], errors="coerce")
        bad = df["adj_factor"].isna() | (df["adj_factor"] <= 0)
        report.range_violations = int(bad.sum())
        if report.range_violations:
            report.notes.append(f"L2: {report.range_violations} invalid adj_factor")
            if self.strict:
                df = df.loc[~bad].reset_index(drop=True)
        return df

    # ---- L3 ----
    def _l3_outlier_ohlcv(
        self,
        df: pd.DataFrame,
        *,
        market: str,
        report: CleaningReport,
    ) -> pd.DataFrame:
        if df.empty or "close" not in df.columns:
            return df
        threshold = MAX_DAILY_CHANGE.get(market.upper(), 0.50)
        df = df.copy()
        df = df.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
        df["_prev_close"] = df.groupby("symbol")["close"].shift(1)
        with np.errstate(divide="ignore", invalid="ignore"):
            df["_pct"] = (df["close"] - df["_prev_close"]).abs() / df["_prev_close"].abs()
        outliers = (df["_pct"] > threshold).fillna(False)
        n_out = int(outliers.sum())
        report.outliers_marked = n_out
        if n_out:
            report.notes.append(
                f"L3: {n_out} rows abs(pct_change) > {threshold:.0%} (market={market})"
            )
            if "outlier" not in df.columns:
                df["outlier"] = False
            df.loc[outliers, "outlier"] = True
            if self.strict:
                df = df.loc[~outliers]
        return df.drop(columns=["_prev_close", "_pct"], errors="ignore").reset_index(drop=True)
