"""
Shared data loading utilities for inference and backtesting.

Extracted from inference_parquet.py template to avoid code duplication.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_DEFAULT_DATA_DIR = "/app/db/feature_snapshots"


def resolve_parquet_path(data_dir: Path, trade_date: str, meta: dict | None = None) -> Path | None:
    """Resolve parquet file path based on market context and date."""
    meta = meta or {}
    market = ""
    ctx = meta.get("context")
    if isinstance(ctx, dict):
        market = str(ctx.get("market", "")).upper()

    _MARKET_PARQUET: dict[str, str] = {
        "HK": "model_features_hk.parquet",
        "US": "model_features_us.parquet",
        "CRYPTO": "model_features_crypto.parquet",
    }

    if market in _MARKET_PARQUET:
        p = Path(data_dir) / _MARKET_PARQUET[market]
        if p.exists():
            return p
        logger.warning("市场 parquet 文件不存在: %s", p)

    # CN or fallback: year-based parquet
    year = int(trade_date[:4])
    p = Path(data_dir) / f"model_features_{year}.parquet"
    if p.exists():
        return p

    # Legacy: no year suffix
    p = Path(data_dir) / "model_features.parquet"
    if p.exists():
        return p

    return None


def filter_untradable_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Filter untradable rows (suspended, zero volume, ST stocks)."""
    if df.empty:
        return df

    filtered = df.copy()

    if "close" in filtered.columns:
        filtered = filtered.loc[
            pd.to_numeric(filtered["close"], errors="coerce") > 0
        ].copy()

    if "volume" in filtered.columns:
        filtered = filtered.loc[
            pd.to_numeric(filtered["volume"], errors="coerce") > 0
        ].copy()

    if "is_st" in filtered.columns:
        filtered = filtered.loc[
            pd.to_numeric(filtered["is_st"], errors="coerce") != 1
        ].copy()

    return filtered


def load_date_data(
    trade_date: str,
    data_dir: Path | str | None = None,
    meta: dict | None = None,
) -> pd.DataFrame | None:
    """Load feature data for a specific date. Returns None if no data available."""
    data_dir = Path(data_dir) if data_dir else Path(_DEFAULT_DATA_DIR)
    meta = meta or {}

    parquet_path = resolve_parquet_path(data_dir, trade_date, meta)
    if parquet_path is None:
        logger.warning(
            "找不到可用的 parquet 文件 (data_dir=%s, market=%s)",
            data_dir, (meta.get("context") or {}).get("market", ""),
        )
        return None

    df = pd.read_parquet(parquet_path, engine="pyarrow")
    # Non-A-share parquet uses 'instrument' column instead of 'symbol'
    if "symbol" not in df.columns and "instrument" in df.columns:
        df = df.rename(columns={"instrument": "symbol"})
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    day_df = df[df["trade_date"] == trade_date].copy()

    if len(day_df) == 0:
        logger.warning("日期 %s 在 parquet 中无数据", trade_date)
        return None

    before_filter = len(day_df)
    day_df = filter_untradable_rows(day_df)
    after_filter = len(day_df)
    if before_filter != after_filter:
        logger.info(
            "过滤不可交易记录: %d -> %d (剔除 %d 条)",
            before_filter, after_filter, before_filter - after_filter,
        )

    if len(day_df) == 0:
        logger.warning("日期 %s 过滤后无可交易数据", trade_date)
        return None

    return day_df


def preprocess(
    df: pd.DataFrame,
    meta: dict,
) -> tuple[pd.DataFrame, list[str]]:
    """Prepare features according to metadata, return (X_df, symbols)."""
    feature_cols = meta.get("feature_columns") or meta.get("features", [])
    fill_values = meta.get("fill_values", {})

    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        logger.warning("缺少 %d 个特征列，将填 0: %s", len(missing), missing[:8])
        for c in missing:
            df = df.copy()
            df[c] = 0.0

    X_df = df[feature_cols].copy()

    for col, val in fill_values.items():
        if col in X_df.columns:
            X_df[col] = X_df[col].fillna(val)
    X_df = X_df.fillna(0.0)

    symbols = df["symbol"].tolist()
    return X_df, symbols


def get_available_dates(
    data_dir: Path | str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    meta: dict | None = None,
) -> list[str]:
    """Get list of available trading dates from parquet data."""
    data_dir = Path(data_dir) if data_dir else Path(_DEFAULT_DATA_DIR)
    meta = meta or {}

    # Collect all parquet files
    parquet_files = sorted(data_dir.glob("model_features_*.parquet"))
    if not parquet_files:
        legacy = data_dir / "model_features.parquet"
        if legacy.exists():
            parquet_files = [legacy]

    if not parquet_files:
        return []

    dates: set[str] = set()
    for pf in parquet_files:
        try:
            df = pd.read_parquet(pf, columns=["trade_date"], engine="pyarrow")
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
            dates.update(df["trade_date"].unique())
        except Exception as e:
            logger.warning("读取 parquet 日期失败 %s: %s", pf.name, e)

    sorted_dates = sorted(dates)
    if start_date:
        sorted_dates = [d for d in sorted_dates if d >= start_date]
    if end_date:
        sorted_dates = [d for d in sorted_dates if d <= end_date]

    return sorted_dates
