#!/usr/bin/env python3
"""
Sync recent HK stock data from yfinance to fill the gap after parquet data ends.

Usage:
    python backend/scripts/sync_hk_recent.py [--since 2026-05-09]
"""

import argparse
import logging
import os
import sys
import time
from datetime import date, datetime
from urllib.parse import quote_plus as _q

import numpy as np
import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Suppress noisy yfinance error logs
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.WARNING)


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


def get_all_hk_symbols(engine) -> list[str]:
    """Get all HK symbols from the database."""
    from sqlalchemy import text as sql_text

    with engine.begin() as conn:
        rows = conn.execute(
            sql_text("SELECT DISTINCT symbol FROM stock_daily_latest_hk ORDER BY symbol")
        ).fetchall()
    return [r[0] for r in rows]


def _to_yf_symbol(sym: str) -> str:
    """Convert DB symbol to yfinance format: 00001 -> 0001.HK, 9988 -> 9988.HK."""
    # DB stores 5-digit (00001) or 4-digit (9988) codes
    # yfinance expects 4-digit: 0001.HK, 0700.HK, 9988.HK
    s = sym[-4:]  # Take last 4 digits
    return f"{s}.HK"


def fetch_hk_data(symbols: list[str], since: str) -> pd.DataFrame:
    """Fetch recent HK data from yfinance for all symbols."""
    frames = []
    total = len(symbols)
    errors = 0

    for i, sym in enumerate(symbols):
        ticker_sym = _to_yf_symbol(sym)
        try:
            df = yf.download(ticker_sym, start=since, progress=False, auto_adjust=True)
            if df is None or df.empty:
                continue

            df = df.reset_index()
            # Normalize column names (yfinance may return MultiIndex for single ticker)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]

            df["symbol"] = sym
            df["trade_date"] = pd.to_datetime(df["Date"]).dt.date
            df["name"] = sym
            df["adj_factor"] = 1.0

            # Rename columns
            col_map = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
            df = df.rename(columns=col_map)

            # yfinance doesn't provide amount, estimate from close * volume
            df["amount"] = df["close"] * df["volume"]

            # pct_change from close prices
            df = df.sort_values("trade_date")
            df["pct_change"] = df["close"].pct_change() * 100

            cols = ["symbol", "trade_date", "name", "open", "high", "low", "close",
                     "volume", "amount", "adj_factor", "pct_change"]
            frames.append(df[cols])
        except Exception as e:
            errors += 1
            if errors <= 5:
                log.warning("Failed to fetch %s: %s", ticker_sym, e)

        if (i + 1) % 100 == 0:
            log.info("  Progress: %d / %d symbols (%d fetched, %d errors)", i + 1, total, len(frames), errors)
            time.sleep(1)  # Rate limiting

    if not frames:
        log.error("No data fetched")
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    result = result.dropna(subset=["close"])
    result = result.drop_duplicates(subset=["symbol", "trade_date"], keep="last")
    log.info("Fetched %d rows for %d symbols (%d errors)", len(result), len(frames), errors)
    return result


def upsert_data(engine, df: pd.DataFrame, batch_size: int = 2000):
    """Upsert data into stock_daily_latest_hk."""
    from sqlalchemy import text as sql_text

    total = len(df)
    log.info("Upserting %d rows...", total)

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

    elapsed = time.time() - t0
    log.info("Upsert complete: %d rows in %.1fs", total, elapsed)


def compute_indicators_for_range(engine, since: str):
    """Compute technical indicators for data since given date (needs prior history for MA/RSI)."""
    from sqlalchemy import text as sql_text

    log.info("Computing indicators for data since %s...", since)

    # Load ALL data (not just since) to get correct MA/RSI values
    with engine.begin() as conn:
        rows = conn.execute(
            sql_text("""
                SELECT symbol, trade_date, open, high, low, close, volume, amount
                FROM stock_daily_latest_hk
                ORDER BY symbol, trade_date
            """)
        ).fetchall()

    if not rows:
        log.warning("No data")
        return

    df = pd.DataFrame(rows, columns=["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount"])
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    for c in ("open", "high", "low", "close", "volume", "amount"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    since_date = pd.to_datetime(since).date()
    log.info("Computing indicators for %d rows, %d symbols...", len(df), df["symbol"].nunique())

    # Helper functions
    def _ema(series, span):
        return series.ewm(span=span, adjust=False).mean()

    def _rsi(series, period=14):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def _kdj(high, low, close, n=9):
        low_n = low.rolling(n, min_periods=1).min()
        high_n = high.rolling(n, min_periods=1).max()
        rsv = (close - low_n) / (high_n - low_n).replace(0, np.nan) * 100
        k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
        d = k.ewm(alpha=1 / 3, adjust=False).mean()
        j = 3 * k - 2 * d
        return k, d, j

    def _macd(close):
        ema12 = _ema(close, 12)
        ema26 = _ema(close, 26)
        dif = ema12 - ema26
        dea = _ema(dif, 9)
        hist = dif - dea
        return dif, dea, hist

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

        # VPIN
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
        g["ep_ttm"] = np.nan
        g["bp"] = np.nan
        g["ln_mv_total"] = np.log(g["amount"].clip(lower=1))
        g["ln_mv_float"] = g["ln_mv_total"] * 0.9

        # Only keep rows from since_date onwards for write-back
        g = g[g["trade_date"] >= since_date]
        results.append(g)

        if (idx + 1) % 500 == 0:
            log.info("  Processed %d / %d symbols", idx + 1, len(symbols))

    df_all = pd.concat(results, ignore_index=True)
    log.info("Indicators computed for %d rows (since %s)", len(df_all), since)

    # Write back using temp table + bulk UPDATE
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
    write_cols = ["symbol", "trade_date"] + update_cols
    df_write = df_all[write_cols].copy()
    for col in update_cols:
        df_write[col] = pd.to_numeric(df_write[col], errors="coerce")
        df_write[col] = df_write[col].replace([np.inf, -np.inf], np.nan)

    log.info("Writing indicators to temp table...")
    df_write.to_sql("_tmp_hk_indicators", engine, if_exists="replace", index=False, method="multi", chunksize=5000)
    log.info("Temp table written: %d rows in %.1fs", len(df_write), time.time() - t0)

    set_parts = [f"{col} = t.{col}" for col in update_cols]
    set_clause = ", ".join(set_parts)

    log.info("Running bulk UPDATE...")
    t1 = time.time()
    with engine.begin() as conn:
        result = conn.execute(sql_text(f"""
            UPDATE stock_daily_latest_hk AS h
            SET {set_clause}
            FROM _tmp_hk_indicators AS t
            WHERE h.symbol = t.symbol AND h.trade_date = t.trade_date
        """))
        rowcount = result.rowcount
        conn.execute(sql_text("DROP TABLE IF EXISTS _tmp_hk_indicators"))

    log.info("Indicators written: %d rows in %.1fs (bulk: %.1fs)", rowcount, time.time() - t0, time.time() - t1)


def main():
    parser = argparse.ArgumentParser(description="Sync recent HK stock data from yfinance")
    parser.add_argument("--since", default="2026-05-09", help="Fetch data since this date (default: 2026-05-09)")
    args = parser.parse_args()

    engine = get_engine()

    # Get all HK symbols from DB
    symbols = get_all_hk_symbols(engine)
    log.info("Found %d HK symbols in database", len(symbols))

    # Fetch recent data
    log.info("=== Step 1: Fetching HK data since %s from yfinance ===", args.since)
    df = fetch_hk_data(symbols, args.since)
    if df.empty:
        log.error("No data fetched, exiting")
        return

    # Upsert
    log.info("=== Step 2: Upserting %d rows ===", len(df))
    upsert_data(engine, df)

    # Compute indicators
    log.info("=== Step 3: Computing indicators ===")
    compute_indicators_for_range(engine, args.since)

    log.info("=== Done ===")


if __name__ == "__main__":
    main()
