#!/usr/bin/env python3
"""Create market-specific stock pool tables from feature parquet files.

Usage:
    python create_market_stock_tables.py
    python create_market_stock_tables.py --market hk
    python create_market_stock_tables.py --market us
    python create_market_stock_tables.py --market crypto
    python create_market_stock_tables.py --all
"""

import argparse
import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
from sqlalchemy import text

try:
    from backend.shared.database_pool import get_db
except ImportError:
    from shared.database_pool import get_db

FEATURE_SNAPSHOT_DIR = _project_root / "db" / "feature_snapshots"

MARKET_CONFIG = {
    "hk": {
        "parquet": "model_features_hk.parquet",
        "table": "stock_daily_latest_hk",
        "symbol_col": "instrument",
    },
    "us": {
        "parquet": "model_features_us.parquet",
        "table": "stock_daily_latest_us",
        "symbol_col": "instrument",
    },
    "crypto": {
        "parquet": "model_features_crypto.parquet",
        "table": "stock_daily_latest_crypto",
        "symbol_col": "instrument",
    },
}

# Columns to extract from parquet and their PostgreSQL types
COLUMN_MAP = {
    "symbol": "VARCHAR(20)",
    "trade_date": "DATE",
    "name": "VARCHAR(100)",
    "open": "DOUBLE PRECISION",
    "high": "DOUBLE PRECISION",
    "low": "DOUBLE PRECISION",
    "close": "DOUBLE PRECISION",
    "volume": "DOUBLE PRECISION",
    "amount": "DOUBLE PRECISION",
    "adj_factor": "DOUBLE PRECISION",
    "turnover_rate": "DOUBLE PRECISION",
    "pe_ttm": "DOUBLE PRECISION",
    "pb": "DOUBLE PRECISION",
    "roe": "DOUBLE PRECISION",
    "total_mv": "DOUBLE PRECISION",
    "float_mv": "DOUBLE PRECISION",
    "industry": "VARCHAR(100)",
    "idx_hs300": "INTEGER",
    "idx_zz1000": "INTEGER",
    "is_st": "INTEGER",
}


def create_table(session, table_name: str):
    """Create the market-specific table if it doesn't exist."""
    cols = ", ".join(f"{col} {dtype}" for col, dtype in COLUMN_MAP.items())
    ddl = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        {cols}
    )
    """
    session.execute(text(ddl))
    session.commit()
    print(f"  Table {table_name} created (or already exists)")


def _fetch_stock_names(symbols: list[str], market: str) -> dict[str, str]:
    """Fetch stock names from yfinance for US/HK stocks, or extract base asset for crypto."""
    name_map: dict[str, str] = {}

    if market == "crypto":
        # Crypto: BTCUSDT → BTC
        for sym in symbols:
            s = str(sym).upper()
            if s.endswith("USDT"):
                name_map[sym] = s[:-4]
            elif s.endswith("BUSD") or s.endswith("USD"):
                name_map[sym] = s[:-4]
            else:
                name_map[sym] = s
        return name_map

    # For US/HK stocks, try yfinance
    try:
        import yfinance as yf
    except ImportError:
        print("  yfinance not installed, using symbols as names")
        return {sym: str(sym) for sym in symbols}

    total = len(symbols)
    print(f"  Fetching stock names from yfinance ({total} symbols)...")
    for i, sym in enumerate(symbols):
        try:
            ticker_sym = str(sym)
            # HK stocks: 0001.HK format
            if market == "hk":
                ticker_sym = f"{sym}.HK"
            ticker = yf.Ticker(ticker_sym)
            info = ticker.info
            name = info.get("shortName") or info.get("longName") or str(sym)
            name_map[sym] = name
        except Exception:
            name_map[sym] = str(sym)
        if (i + 1) % 50 == 0:
            print(f"    Progress: {i + 1}/{total}")

    print(f"  Fetched {len(name_map)} stock names")
    return name_map


def load_parquet_to_table(market: str):
    """Load parquet data into the market-specific PostgreSQL table."""
    config = MARKET_CONFIG[market]
    parquet_path = FEATURE_SNAPSHOT_DIR / config["parquet"]
    table_name = config["table"]
    symbol_col = config["symbol_col"]

    if not parquet_path.exists():
        print(f"  Parquet file not found: {parquet_path}")
        return False

    print(f"  Loading {parquet_path.name}...")
    df = pd.read_parquet(parquet_path)
    print(f"  Read {len(df)} rows, {len(df.columns)} columns")

    # Get latest date per symbol
    if "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        latest_date = df["trade_date"].max()
        df_latest = df[df["trade_date"] == latest_date].copy()
        print(f"  Latest date: {latest_date.date()}, {len(df_latest)} symbols")
    else:
        df_latest = df.copy()

    # Rename instrument -> symbol
    if symbol_col in df_latest.columns:
        df_latest = df_latest.rename(columns={symbol_col: "symbol"})

    # Fetch stock names from data API
    symbols = df_latest["symbol"].unique().tolist()
    name_map = _fetch_stock_names(symbols, market)

    # Add missing columns with defaults
    for col in COLUMN_MAP:
        if col not in df_latest.columns:
            if col == "name":
                df_latest[col] = df_latest["symbol"].map(name_map)
            elif col in ("idx_hs300", "idx_zz1000", "is_st"):
                df_latest[col] = 0
            else:
                df_latest[col] = 0.0

    # Select only the columns we need
    cols_to_keep = [c for c in COLUMN_MAP if c in df_latest.columns]
    df_out = df_latest[cols_to_keep].copy()

    # Ensure symbol is string
    df_out["symbol"] = df_out["symbol"].astype(str)

    # Insert into PostgreSQL
    with get_db() as session:
        # Create table
        create_table(session, table_name)

        # Clear existing data
        session.execute(text(f"DELETE FROM {table_name}"))
        session.commit()

        # Insert in batches
        batch_size = 1000
        total_inserted = 0
        for i in range(0, len(df_out), batch_size):
            batch = df_out.iloc[i : i + batch_size]
            cols = ", ".join(batch.columns)
            placeholders = ", ".join([f":{col}" for col in batch.columns])
            insert_sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"

            for _, row in batch.iterrows():
                params = {col: (None if pd.isna(row[col]) else row[col]) for col in batch.columns}
                session.execute(text(insert_sql), params)

            session.commit()
            total_inserted += len(batch)
            print(f"  Inserted {total_inserted}/{len(df_out)} rows")

        # Create index on symbol
        session.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol ON {table_name} (symbol)"))
        session.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_trade_date ON {table_name} (trade_date)"))
        session.commit()

    print(f"  Done: {table_name} has {len(df_out)} rows")
    return True


def main():
    parser = argparse.ArgumentParser(description="Create market-specific stock tables")
    parser.add_argument("--market", choices=["hk", "us", "crypto"], help="Specific market to load")
    parser.add_argument("--all", action="store_true", help="Load all markets")
    args = parser.parse_args()

    if not args.market and not args.all:
        args.all = True

    markets = list(MARKET_CONFIG.keys()) if args.all else [args.market]

    for market in markets:
        print(f"\n=== Processing {market.upper()} market ===")
        try:
            load_parquet_to_table(market)
        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
