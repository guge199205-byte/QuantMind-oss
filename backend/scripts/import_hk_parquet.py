#!/usr/bin/env python3
"""
Import HK stock data from local parquet files into stock_daily_latest_hk.

Source: /mnt/g/A_H/quant_data_lake/frequency=daily/market=HK_share/
Format: Parquet files organized by year (year=YYYY/data.parquet)

Columns in parquet: datetime, symbol, open, high, low, close, volume, amount, pre_close, pct_chg, market
Target table: stock_daily_latest_hk

Usage:
    python backend/scripts/import_hk_parquet.py [--since 2020] [--indicators-only]
"""

import argparse
import logging
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote_plus as _q

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

PARQUET_ROOT = "/mnt/g/A_H/quant_data_lake/frequency=daily/market=HK_share"


def get_engine():
    from sqlalchemy import create_engine

    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        host = os.getenv("DB_MASTER_HOST", "quantmind-db")
        port = os.getenv("DB_MASTER_PORT", "5432")
        user = os.getenv("DB_USER", "quantmind")
        pwd = _q(os.getenv("DB_PASSWORD", "quantmind"))
        name = os.getenv("DB_NAME", "quantmind")
        db_url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"
    elif "asyncpg" in db_url:
        db_url = db_url.replace("asyncpg", "psycopg2")
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return create_engine(db_url, pool_pre_ping=True)


def load_parquet_data(since_year: int = 2020) -> pd.DataFrame:
    """Load and combine parquet files from the HK data lake."""
    root = Path(PARQUET_ROOT)
    if not root.exists():
        log.error("Parquet root not found: %s", root)
        sys.exit(1)

    frames = []
    for year_dir in sorted(root.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.startswith("year="):
            continue
        year = int(year_dir.name.split("=")[1])
        if year < since_year:
            continue
        pq_file = year_dir / "data.parquet"
        if not pq_file.exists():
            log.warning("Missing parquet: %s", pq_file)
            continue
        df = pd.read_parquet(pq_file)
        frames.append(df)
        log.info("Loaded %s: %d rows", year_dir.name, len(df))

    if not frames:
        log.error("No parquet files found since year %d", since_year)
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True)
    log.info("Total loaded: %d rows", len(combined))
    return combined


def transform_for_db(df: pd.DataFrame) -> pd.DataFrame:
    """Transform parquet data to match stock_daily_latest_hk schema."""
    # Strip 'HK' prefix from symbol: HK00001 -> 00001
    df = df.copy()
    df["symbol"] = df["symbol"].str.replace("HK", "", n=1).str.zfill(5)

    # Rename datetime -> trade_date
    df["trade_date"] = pd.to_datetime(df["datetime"]).dt.date

    # pct_chg is a ratio (0.001 = 0.1%), convert to percentage
    df["pct_change"] = df["pct_chg"] * 100

    # Set name = symbol for now (will be updated separately)
    df["name"] = df["symbol"]

    # adj_factor = 1.0 (no adjustment data available)
    df["adj_factor"] = 1.0

    # Select and order columns to match table
    cols = [
        "symbol", "trade_date", "name", "open", "high", "low", "close",
        "volume", "amount", "adj_factor", "pct_change",
    ]
    result = df[cols].copy()

    # Drop duplicates (same symbol + trade_date)
    before = len(result)
    result = result.drop_duplicates(subset=["symbol", "trade_date"], keep="last")
    if len(result) < before:
        log.info("Dropped %d duplicate rows", before - len(result))

    result = result.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    return result


def upsert_data(engine, df: pd.DataFrame, batch_size: int = 2000):
    """Upsert data into stock_daily_latest_hk using ON CONFLICT."""
    from sqlalchemy import text as sql_text

    total = len(df)
    log.info("Upserting %d rows into stock_daily_latest_hk...", total)

    upsert_sql = sql_text("""
        INSERT INTO stock_daily_latest_hk
            (symbol, trade_date, name, open, high, low, close, volume, amount, adj_factor, pct_change)
        VALUES
            (:symbol, :trade_date, :name, :open, :high, :low, :close, :volume, :amount, :adj_factor, :pct_change)
        ON CONFLICT (symbol, trade_date) DO UPDATE SET
            name = EXCLUDED.name,
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            amount = EXCLUDED.amount,
            adj_factor = EXCLUDED.adj_factor,
            pct_change = EXCLUDED.pct_change
    """)

    t0 = time.time()
    with engine.begin() as conn:
        for i in range(0, total, batch_size):
            batch = df.iloc[i : i + batch_size]
            records = batch.to_dict("records")
            conn.execute(upsert_sql, records)
            if (i // batch_size) % 10 == 0:
                log.info("  Progress: %d / %d rows", min(i + batch_size, total), total)

    elapsed = time.time() - t0
    log.info("Upsert complete: %d rows in %.1fs", total, elapsed)


# ── Technical Indicator Calculations ──


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _kdj(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9) -> tuple:
    low_n = low.rolling(n, min_periods=1).min()
    high_n = high.rolling(n, min_periods=1).max()
    rsv = (close - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    d = k.ewm(alpha=1 / 3, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def _macd(close: pd.Series) -> tuple:
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    dif = ema12 - ema26
    dea = _ema(dif, 9)
    hist = dif - dea
    return dif, dea, hist


def compute_indicators(engine, since_year: int = 2020):
    """Compute technical indicators for HK data."""
    from sqlalchemy import text as sql_text

    cutoff = date(since_year, 1, 1)
    log.info("Computing indicators for data since %s...", cutoff)

    with engine.begin() as conn:
        rows = conn.execute(
            sql_text("""
                SELECT symbol, trade_date, open, high, low, close, volume, amount
                FROM stock_daily_latest_hk
                WHERE trade_date >= :cutoff
                ORDER BY symbol, trade_date
            """),
            {"cutoff": cutoff},
        ).fetchall()

    if not rows:
        log.warning("No data to compute indicators for")
        return

    df = pd.DataFrame(
        rows,
        columns=["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount"],
    )
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    for c in ("open", "high", "low", "close", "volume", "amount"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    log.info("Computing indicators for %d rows, %d symbols...", len(df), df["symbol"].nunique())

    # Group by symbol and compute indicators
    results = []
    symbols = df["symbol"].unique()
    for idx, sym in enumerate(symbols):
        g = df[df["symbol"] == sym].sort_values("trade_date").copy()
        c = g["close"]
        h = g["high"]
        lo = g["low"]
        v = g["volume"]

        # MA
        for p in (5, 10, 20, 60):
            g[f"ma{p}"] = c.rolling(p, min_periods=1).mean()
            g[f"ma_gap_{p}"] = ((c / g[f"ma{p}"]) - 1) * 100

        # Returns
        g["return_1d"] = c.pct_change(1) * 100
        g["return_3d"] = c.pct_change(3) * 100
        g["return_5d"] = c.pct_change(5) * 100

        # RSI
        g["rsi_6"] = _rsi(c, 6)
        g["rsi_14"] = _rsi(c, 14)

        # MACD
        dif, dea, hist = _macd(c)
        g["macd_dif"] = dif
        g["macd_dea"] = dea
        g["macd_hist"] = hist

        # KDJ
        k, d, j = _kdj(h, lo, c)
        g["kdj_k"] = k
        g["kdj_d"] = d
        g["kdj_j"] = j

        # Volume ratio
        g["volume_ratio_5"] = v / v.rolling(5, min_periods=1).mean().clip(lower=1) - 1
        g["volume_ratio_20"] = v / v.rolling(20, min_periods=1).mean().clip(lower=1) - 1

        # ATR
        tr = pd.concat([h - lo, (h - c.shift()).abs(), (lo - c.shift()).abs()], axis=1).max(axis=1)
        g["vol_atr_14"] = tr.rolling(14, min_periods=1).mean()
        g["vol_atr_20"] = tr.rolling(20, min_periods=1).mean()

        # VPIN (simplified)
        direction = np.sign(c.diff())
        buy_vol = v * (direction > 0).astype(float)
        sell_vol = v * (direction <= 0).astype(float)
        total_vol = v.rolling(20, min_periods=5).sum().clip(lower=1)
        g["flow_vpin"] = (buy_vol - sell_vol).abs().rolling(20, min_periods=5).sum() / total_vol
        g["flow_vpin_ma_5"] = g["flow_vpin"].rolling(5, min_periods=1).mean()
        g["flow_vpin_ma_20"] = g["flow_vpin"].rolling(20, min_periods=1).mean()

        # Style factors
        ret = c.pct_change()
        ln_c = np.log(c.clip(lower=1e-8))
        log_ret = ln_c.diff()

        g["style_beta_20"] = ret.rolling(20, min_periods=5).mean() / ret.rolling(20, min_periods=5).std().replace(0, np.nan)
        g["style_beta_60"] = ret.rolling(60, min_periods=10).mean() / ret.rolling(60, min_periods=10).std().replace(0, np.nan)
        g["style_idio_vol_20"] = log_ret.rolling(20, min_periods=5).std()
        g["style_idio_vol_60"] = log_ret.rolling(60, min_periods=10).std()
        g["vol_std_20"] = ret.rolling(20, min_periods=5).std() * 100
        g["vol_downside_20"] = log_ret.clip(upper=0).rolling(20, min_periods=5).std()

        # Momentum
        g["mom_ret_1d"] = ret
        g["mom_ret_5d"] = c.pct_change(5)
        g["mom_ret_20d"] = c.pct_change(20)
        g["mom_ret_60d"] = c.pct_change(60)
        g["mom_ma_gap_5"] = (c / c.rolling(5, min_periods=1).mean()) - 1
        g["mom_ma_gap_20"] = (c / c.rolling(20, min_periods=1).mean()) - 1

        # Value
        g["ep_ttm"] = np.nan  # Needs fundamental data
        g["bp"] = np.nan
        g["ln_mv_total"] = np.log(g["amount"].clip(lower=1))
        g["ln_mv_float"] = g["ln_mv_total"] * 0.9

        results.append(g)

        if (idx + 1) % 500 == 0:
            log.info("  Processed %d / %d symbols", idx + 1, len(symbols))

    df_all = pd.concat(results, ignore_index=True)
    log.info("Indicators computed for %d rows", len(df_all))

    # Write back to database using temp table + bulk UPDATE (much faster than row-by-row)
    update_cols = [
        "ma5", "ma10", "ma20", "ma60",
        "ma_gap_5", "ma_gap_10", "ma_gap_20",
        "return_1d", "return_3d", "return_5d",
        "rsi_6", "rsi_14",
        "macd_dif", "macd_dea", "macd_hist",
        "kdj_k", "kdj_d", "kdj_j",
        "volume_ratio_5", "volume_ratio_20",
        "vol_atr_14", "vol_atr_20",
        "flow_vpin", "flow_vpin_ma_5", "flow_vpin_ma_20",
        "style_beta_20", "style_beta_60",
        "style_idio_vol_20", "style_idio_vol_60",
        "vol_std_20", "vol_downside_20",
        "mom_ret_1d", "mom_ret_5d", "mom_ret_20d", "mom_ret_60d",
        "mom_ma_gap_5", "mom_ma_gap_20",
        "ln_mv_total", "ln_mv_float",
    ]

    t0 = time.time()

    # Replace inf with NaN, then prepare write-back columns
    write_cols = ["symbol", "trade_date"] + update_cols
    df_write = df_all[write_cols].copy()
    for col in update_cols:
        df_write[col] = pd.to_numeric(df_write[col], errors="coerce")
        df_write[col] = df_write[col].replace([np.inf, -np.inf], np.nan)

    # Write to a temp table using pandas to_sql (uses COPY internally - fast)
    log.info("Writing indicators to temp table...")
    df_write.to_sql(
        "_tmp_hk_indicators",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5000,
    )
    log.info("Temp table written: %d rows in %.1fs", len(df_write), time.time() - t0)

    # Build SET clause for bulk UPDATE
    set_parts = [f"{col} = t.{col}" for col in update_cols]
    set_clause = ", ".join(set_parts)

    # Single bulk UPDATE from temp table
    log.info("Running bulk UPDATE from temp table...")
    t1 = time.time()
    with engine.begin() as conn:
        result = conn.execute(sql_text(f"""
            UPDATE stock_daily_latest_hk AS h
            SET {set_clause}
            FROM _tmp_hk_indicators AS t
            WHERE h.symbol = t.symbol AND h.trade_date = t.trade_date
        """))
        rowcount = result.rowcount
        # Drop temp table
        conn.execute(sql_text("DROP TABLE IF EXISTS _tmp_hk_indicators"))

    elapsed = time.time() - t0
    log.info("Indicators written: %d rows updated in %.1fs (bulk update: %.1fs)", rowcount, elapsed, time.time() - t1)


def main():
    parser = argparse.ArgumentParser(description="Import HK parquet data")
    parser.add_argument("--since", type=int, default=2020, help="Import data since this year (default: 2020)")
    parser.add_argument("--indicators-only", action="store_true", help="Only compute indicators, skip data import")
    parser.add_argument("--data-only", action="store_true", help="Only import data, skip indicator computation")
    args = parser.parse_args()

    engine = get_engine()

    if not args.indicators_only:
        log.info("=== Step 1: Importing HK parquet data since %d ===", args.since)
        df = load_parquet_data(since_year=args.since)
        df_db = transform_for_db(df)
        log.info("Transformed: %d rows, %d symbols", len(df_db), df_db["symbol"].nunique())
        upsert_data(engine, df_db)

    if not args.data_only:
        log.info("=== Step 2: Computing technical indicators ===")
        compute_indicators(engine, since_year=args.since)

    log.info("=== Done ===")


if __name__ == "__main__":
    main()
