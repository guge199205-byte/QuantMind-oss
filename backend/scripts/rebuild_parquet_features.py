#!/usr/bin/env python3
"""Rebuild historical year parquet files to include fundamental/index/concept columns.

Reads existing model_features_{year}.parquet files and merges in columns from
stock_daily_latest (fundamentals, index membership, concept tags).

Usage:
    python rebuild_parquet_features.py              # Rebuild all years
    python rebuild_parquet_features.py --year 2024  # Rebuild specific year
    python rebuild_parquet_features.py --dry-run    # Check only
"""

import argparse
import asyncio
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# Container vs host
if os.path.exists("/app") and not os.environ.get("QUANTMIND_HOST_MODE"):
    PARQUET_DIR = Path("/app/db/feature_snapshots")
    DB_URL = "postgresql://quantmind:quantmind2026@db:5432/quantmind"
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    PARQUET_DIR = PROJECT_ROOT / "db" / "feature_snapshots"
    DB_URL = "postgresql://quantmind:quantmind2026@localhost:5432/quantmind"

# Columns to add from stock_daily_latest
ADD_COLS = [
    "symbol", "trade_date",
    # Fundamentals
    "pe_ttm", "pb", "roe", "bp", "ep_ttm", "ln_mv_total", "float_mv", "total_mv",
    "turnover_rate", "is_st", "industry", "listing_market",
    # Index membership
    "idx_all", "idx_hs300", "idx_zz1000", "idx_chinext", "idx_margin",
    # Concept tags
    "concept_ai", "concept_chip", "concept_new_energy", "concept_pv",
    "concept_military", "concept_medical", "concept_fintech",
    "concept_consumption", "concept_state_owned", "concept_lithium",
]


def _log(msg: str) -> None:
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


async def fetch_db_data(since: date, until: date, lookback_days: int = 120) -> pd.DataFrame:
    """Fetch fundamental/index/concept data from stock_daily_latest."""
    import asyncpg

    conn = await asyncpg.connect(DB_URL)
    try:
        cols_str = ", ".join(ADD_COLS)
        rows = await conn.fetch(f"""
            SELECT {cols_str}
            FROM stock_daily_latest
            WHERE trade_date BETWEEN $1 AND $2
            ORDER BY symbol, trade_date
        """, since - timedelta(days=lookback_days), until)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame([dict(r) for r in rows])
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df
    finally:
        await conn.close()


# Alpha158 K-line + Price Relative factors (computed from OHLCV)
ALPHA158_COLS = [
    "kline_kmid", "kline_klen", "kline_kmid2", "kline_kup", "kline_kup2",
    "kline_klow", "kline_klow2", "kline_ksft", "kline_ksft2",
    "prel_open0", "prel_high0", "prel_low0", "prel_vwap0",
]


def compute_alpha158_for_group(g: pd.DataFrame) -> pd.DataFrame:
    """Compute Alpha158 K-line and price relative factors from OHLCV."""
    g = g.sort_values("trade_date").copy()
    c = g["close"]
    h = g["high"]
    lo = g["low"]
    o = g["open"]
    v = g["volume"]
    amt = g.get("amount", (h + lo + c) / 3 * v)  # fallback if no amount column

    denom = (h - lo).replace(0, np.nan)

    # K-Line Pattern
    g["kline_kmid"] = (c - o) / o.clip(lower=1e-8)
    g["kline_klen"] = (h - lo) / o.clip(lower=1e-8)
    g["kline_kmid2"] = (c - o) / denom
    g["kline_kup"] = (h - pd.concat([o, c], axis=1).max(axis=1)) / o.clip(lower=1e-8)
    g["kline_kup2"] = (h - pd.concat([o, c], axis=1).max(axis=1)) / denom
    g["kline_klow"] = (pd.concat([o, c], axis=1).min(axis=1) - lo) / o.clip(lower=1e-8)
    g["kline_klow2"] = (pd.concat([o, c], axis=1).min(axis=1) - lo) / denom
    g["kline_ksft"] = (2 * c - h - lo) / o.clip(lower=1e-8)
    g["kline_ksft2"] = (2 * c - h - lo) / denom

    # Price Relative
    g["prel_open0"] = o / c.clip(lower=1e-8)
    g["prel_high0"] = h / c.clip(lower=1e-8)
    g["prel_low0"] = lo / c.clip(lower=1e-8)
    vwap = amt / v.clip(lower=1)
    vwap = vwap.replace([np.inf, -np.inf], np.nan).fillna((h + lo + c) / 3)
    g["prel_vwap0"] = vwap / c.clip(lower=1e-8)

    return g


# New factors: price position, sharpe momentum, volume-price, trend quality, lag
NEW_FACTOR_COLS = [
    "price_position_20", "price_position_60",
    "dist_to_high_20", "dist_to_low_20", "ret_rank_20",
    "mom_sharpe_5", "mom_sharpe_20", "mom_sharpe_60", "mom_risk_adj_20",
    "pv_corr_20", "pv_corr_10", "up_volume_ratio_20", "pv_divergence_20",
    "trend_r2_20", "trend_slope_20", "consecutive_updown_5",
    "ret_1d_lag1", "ret_1d_lag2",
]


def compute_new_factors_for_group(g: pd.DataFrame) -> pd.DataFrame:
    """Compute 18 new factors from OHLCV."""
    g = g.sort_values("trade_date").copy()
    c = g["close"]
    h = g["high"]
    lo = g["low"]
    v = g["volume"]
    ret_1d = c.pct_change()

    # Tier 1: Price position
    low_20 = lo.rolling(20, min_periods=1).min()
    high_20 = h.rolling(20, min_periods=1).max()
    g["price_position_20"] = (c - low_20) / (high_20 - low_20).clip(lower=1e-8)
    low_60 = lo.rolling(60, min_periods=1).min()
    high_60 = h.rolling(60, min_periods=1).max()
    g["price_position_60"] = (c - low_60) / (high_60 - low_60).clip(lower=1e-8)
    g["dist_to_high_20"] = c / high_20.clip(lower=1e-8) - 1
    g["dist_to_low_20"] = c / low_20.clip(lower=1e-8) - 1
    # Rank approximation: (value - min) / (max - min) in window
    ret_min_20 = ret_1d.rolling(20, min_periods=5).min()
    ret_max_20 = ret_1d.rolling(20, min_periods=5).max()
    g["ret_rank_20"] = (ret_1d - ret_min_20) / (ret_max_20 - ret_min_20).clip(lower=1e-8)

    # Tier 2: Sharpe momentum
    ret_std_5 = ret_1d.rolling(5, min_periods=2).std()
    ret_std_20 = ret_1d.rolling(20, min_periods=5).std()
    ret_std_60 = ret_1d.rolling(60, min_periods=10).std()
    g["mom_sharpe_5"] = c.pct_change(5) / ret_std_5.clip(lower=1e-6)
    g["mom_sharpe_20"] = c.pct_change(20) / ret_std_20.clip(lower=1e-6)
    g["mom_sharpe_60"] = c.pct_change(60) / ret_std_60.clip(lower=1e-6)
    ret_20 = c.pct_change(20)
    g["mom_risk_adj_20"] = (ret_20 - ret_20.rolling(20, min_periods=5).mean()) / ret_std_20.clip(lower=1e-6)

    # Tier 3: Volume-price
    log_vol = np.log(v.clip(lower=1))
    g["pv_corr_20"] = ret_1d.rolling(20, min_periods=10).corr(log_vol)
    g["pv_corr_10"] = ret_1d.rolling(10, min_periods=5).corr(log_vol)
    up_vol = pd.Series(np.where(ret_1d > 0, v, 0), index=g.index)
    g["up_volume_ratio_20"] = up_vol.rolling(20, min_periods=5).sum() / v.rolling(20, min_periods=5).sum().clip(lower=1e-6)
    # Price rank - volume rank (vectorized approximation)
    c_min_20 = c.rolling(20, min_periods=5).min()
    c_max_20 = c.rolling(20, min_periods=5).max()
    v_min_20 = v.rolling(20, min_periods=5).min()
    v_max_20 = v.rolling(20, min_periods=5).max()
    c_rank = (c - c_min_20) / (c_max_20 - c_min_20).clip(lower=1e-8)
    v_rank = (v - v_min_20) / (v_max_20 - v_min_20).clip(lower=1e-8)
    g["pv_divergence_20"] = c_rank - v_rank

    # Tier 4: Trend quality (vectorized using rolling correlation)
    # R² = corr(price, time_index)²
    time_idx = pd.Series(np.arange(len(c), dtype=float), index=c.index)
    g["trend_r2_20"] = c.rolling(20, min_periods=10).corr(time_idx) ** 2

    # Slope = cov(price, t) / var(t), normalized by mean(price)
    # Using: slope = corr * std(price) / std(t)
    c_std_20 = c.rolling(20, min_periods=10).std()
    t_std = np.sqrt((np.arange(20) - np.arange(20).mean()) ** 2).sum() / 20  # constant for window=20
    corr_ct = c.rolling(20, min_periods=10).corr(time_idx)
    g["trend_slope_20"] = corr_ct * c_std_20 / (t_std + 1e-6) / c.rolling(20, min_periods=10).mean().clip(lower=1e-6)
    up_down = pd.Series(np.where(ret_1d > 0, 1, np.where(ret_1d < 0, -1, 0)), index=g.index)
    g["consecutive_updown_5"] = up_down.rolling(5, min_periods=1).sum()

    # Tier 5: Lag features
    g["ret_1d_lag1"] = ret_1d.shift(1)
    g["ret_1d_lag2"] = ret_1d.shift(2)

    return g


def add_alpha158_to_parquet(year: int, dry_run: bool = False) -> None:
    """Add Alpha158 K-line and price relative factors to an existing year parquet."""
    parquet_path = PARQUET_DIR / f"model_features_{year}.parquet"
    if not parquet_path.exists():
        _log(f"  SKIP: {parquet_path} not found")
        return

    _log(f"Reading {parquet_path}...")
    df = pd.read_parquet(parquet_path, engine="pyarrow")
    _log(f"  {len(df):,} rows, {df['symbol'].nunique()} symbols, {len(df.columns)} columns")

    # Check which columns are missing
    missing = [c for c in ALPHA158_COLS if c not in df.columns]
    if not missing:
        _log(f"  All Alpha158 factors already present, skipping")
        return

    _log(f"  Need to add {len(missing)} factors: {missing}")

    if dry_run:
        _log(f"  DRY RUN - would compute {len(missing)} factors")
        return

    # Check required OHLCV columns exist
    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(set(df.columns)):
        _log(f"  ERROR: Missing OHLCV columns: {required - set(df.columns)}")
        return

    # Compute factors per symbol
    _log(f"  Computing Alpha158 factors...")
    results = []
    total = df["symbol"].nunique()
    done = 0
    for sym, group in df.groupby("symbol"):
        feat = compute_alpha158_for_group(group)
        results.append(feat)
        done += 1
        if done % 2000 == 0:
            _log(f"    Progress: {done}/{total}")

    result = pd.concat(results, ignore_index=True)
    _log(f"  Computed: {len(result):,} rows, {len(result.columns)} columns")

    # Write back
    _log(f"  Writing {parquet_path}...")
    result.to_parquet(parquet_path, engine="pyarrow", compression="zstd", index=False)
    _log(f"  DONE: {len(result):,} rows, {len(result.columns)} columns")


def add_new_factors_to_parquet(year: int, dry_run: bool = False) -> None:
    """Add 18 new factors (price position, sharpe, vol-price, trend, lag) to parquet."""
    parquet_path = PARQUET_DIR / f"model_features_{year}.parquet"
    if not parquet_path.exists():
        _log(f"  SKIP: {parquet_path} not found")
        return

    _log(f"Reading {parquet_path}...")
    df = pd.read_parquet(parquet_path, engine="pyarrow")
    _log(f"  {len(df):,} rows, {df['symbol'].nunique()} symbols, {len(df.columns)} columns")

    missing = [c for c in NEW_FACTOR_COLS if c not in df.columns]
    if not missing:
        _log(f"  All 18 new factors already present, skipping")
        return

    _log(f"  Need to add {len(missing)} factors: {missing[:5]}...")

    if dry_run:
        _log(f"  DRY RUN - would compute {len(missing)} factors")
        return

    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(set(df.columns)):
        _log(f"  ERROR: Missing OHLCV columns: {required - set(df.columns)}")
        return

    _log(f"  Computing new factors...")
    results = []
    total = df["symbol"].nunique()
    done = 0
    for sym, group in df.groupby("symbol"):
        feat = compute_new_factors_for_group(group)
        results.append(feat)
        done += 1
        if done % 2000 == 0:
            _log(f"    Progress: {done}/{total}")

    result = pd.concat(results, ignore_index=True)
    _log(f"  Computed: {len(result):,} rows, {len(result.columns)} columns")

    _log(f"  Writing {parquet_path}...")
    result.to_parquet(parquet_path, engine="pyarrow", compression="zstd", index=False)
    _log(f"  DONE: {len(result):,} rows, {len(result.columns)} columns")


def rebuild_year(year: int, dry_run: bool = False) -> None:
    """Rebuild a single year parquet with additional columns."""
    parquet_path = PARQUET_DIR / f"model_features_{year}.parquet"
    if not parquet_path.exists():
        _log(f"  SKIP: {parquet_path} not found")
        return

    _log(f"Reading {parquet_path}...")
    existing = pd.read_parquet(parquet_path, engine="pyarrow")
    existing["trade_date"] = pd.to_datetime(existing["trade_date"]).dt.date
    _log(f"  {len(existing):,} rows, {existing['symbol'].nunique()} symbols, {len(existing.columns)} columns")

    # Check which columns we need to add
    existing_cols = set(existing.columns)
    new_cols = [c for c in ADD_COLS if c not in existing_cols and c not in ("symbol", "trade_date")]
    if not new_cols:
        _log(f"  All columns already present, skipping")
        return

    _log(f"  Need to add {len(new_cols)} columns: {new_cols[:5]}{'...' if len(new_cols) > 5 else ''}")

    if dry_run:
        _log(f"  DRY RUN - would add {len(new_cols)} columns")
        return

    # Fetch from DB
    since_date = existing["trade_date"].min()
    until_date = existing["trade_date"].max()
    _log(f"  Fetching from DB: {since_date} ~ {until_date}...")
    db_df = asyncio.run(fetch_db_data(since_date, until_date, lookback_days=0))

    if db_df.empty:
        _log(f"  WARNING: No data in DB for this period")
        return

    _log(f"  DB data: {len(db_df):,} rows, {db_df['symbol'].nunique()} symbols")

    # Merge on (symbol, trade_date)
    _log(f"  Merging...")
    merge_cols = ["symbol", "trade_date"] + new_cols
    db_subset = db_df[merge_cols].copy()

    # Convert trade_date to same type for merge
    db_subset["trade_date"] = pd.to_datetime(db_subset["trade_date"]).dt.date

    merged = existing.merge(db_subset, on=["symbol", "trade_date"], how="left")
    _log(f"  Merged: {len(merged):,} rows, {len(merged.columns)} columns")

    # Fill NaN for concept/index columns with 0
    for col in new_cols:
        if col.startswith("concept_") or col.startswith("idx_"):
            merged[col] = merged[col].fillna(0).astype(np.float32)
        elif col == "is_st":
            merged[col] = merged[col].fillna(0).astype(np.int32)
        elif merged[col].dtype in (np.float64, np.float32):
            merged[col] = merged[col].astype(np.float32)

    # Write back
    _log(f"  Writing {parquet_path}...")
    merged.to_parquet(parquet_path, engine="pyarrow", compression="zstd", index=False)
    _log(f"  DONE: {len(merged):,} rows, {len(merged.columns)} columns")


def main():
    parser = argparse.ArgumentParser(description="Rebuild parquet features")
    parser.add_argument("--year", type=int, default=0, help="Rebuild specific year (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Check only")
    parser.add_argument("--alpha158", action="store_true", help="Add Alpha158 K-line/price relative factors only")
    parser.add_argument("--new-factors", action="store_true", help="Add 18 new factors (price position, sharpe, vol-price, trend, lag)")
    args = parser.parse_args()

    if args.year:
        years = [args.year]
    else:
        # Find all year parquets
        years = sorted([
            int(f.stem.split("_")[-1])
            for f in PARQUET_DIR.glob("model_features_20*.parquet")
            if f.stem.split("_")[-1].isdigit()
        ])

    if args.alpha158:
        _log(f"Adding Alpha158 factors to {len(years)} parquet files: {years}")
        for year in years:
            _log(f"\n=== Year {year} ===")
            add_alpha158_to_parquet(year, dry_run=args.dry_run)
    elif args.new_factors:
        _log(f"Adding 18 new factors to {len(years)} parquet files: {years}")
        for year in years:
            _log(f"\n=== Year {year} ===")
            add_new_factors_to_parquet(year, dry_run=args.dry_run)
    else:
        _log(f"Will rebuild {len(years)} parquet files: {years}")
        for year in years:
            _log(f"\n=== Year {year} ===")
            rebuild_year(year, dry_run=args.dry_run)

    _log("\nAll done!")


if __name__ == "__main__":
    main()
