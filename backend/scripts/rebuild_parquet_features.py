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
    else:
        _log(f"Will rebuild {len(years)} parquet files: {years}")
        for year in years:
            _log(f"\n=== Year {year} ===")
            rebuild_year(year, dry_run=args.dry_run)

    _log("\nAll done!")


if __name__ == "__main__":
    main()
