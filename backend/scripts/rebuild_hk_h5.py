#!/usr/bin/env python3
"""
从 PostgreSQL stock_daily_latest_hk 表重建 H5 文件和 Qlib bin 格式。

用法:
    python backend/scripts/rebuild_hk_h5.py [--qlib]
    --qlib: 同时生成 Qlib bin 格式
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus as _q

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# 容器内 vs 主机
_script_root = Path(__file__).resolve().parents[2]
if (_script_root / "db").is_dir():
    PROJECT_ROOT = _script_root
elif Path("/app/db").is_dir():
    PROJECT_ROOT = Path("/app")
else:
    PROJECT_ROOT = _script_root

H5_PATH = PROJECT_ROOT / "db" / "hk_data" / "daily_pv.h5"
QLIB_DIR = PROJECT_ROOT / "db" / "qlib_data" / "hk_data"


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


def load_from_db(engine) -> pd.DataFrame:
    """从 PostgreSQL 加载全部 HK 数据。"""
    from sqlalchemy import text as sql_text

    log.info("Loading data from stock_daily_latest_hk...")
    t0 = time.time()

    with engine.begin() as conn:
        rows = conn.execute(
            sql_text("""
                SELECT symbol, trade_date, open, high, low, close, volume, amount,
                       adj_factor, pct_change
                FROM stock_daily_latest_hk
                ORDER BY symbol, trade_date
            """)
        ).fetchall()

    log.info("Loaded %d rows in %.1fs", len(rows), time.time() - t0)

    df = pd.DataFrame(
        rows,
        columns=[
            "symbol", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "adj_factor", "pct_change",
        ],
    )
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    for c in ("open", "high", "low", "close", "volume", "amount", "adj_factor", "pct_change"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def convert_to_h5_format(df: pd.DataFrame) -> pd.DataFrame:
    """转换为 RD-Agent 兼容的 H5 格式 (MultiIndex: datetime, instrument; $前缀列名)。"""
    # symbol (5-digit) -> instrument (4-digit, no leading zero for display)
    # H5 uses 4-digit format: 0001, 0700, 9988
    df = df.copy()
    df["instrument"] = df["symbol"].str.lstrip("0").str.zfill(4)
    df["datetime"] = pd.to_datetime(df["trade_date"])

    # $ prefix columns (RD-Agent convention)
    col_map = {
        "open": "$open",
        "high": "$high",
        "low": "$low",
        "close": "$close",
        "volume": "$volume",
        "adj_factor": "$factor",
    }
    for old, new in col_map.items():
        df[new] = df[old]

    h5_cols = ["datetime", "instrument", "$open", "$high", "$low", "$close", "$volume", "$factor"]
    result = df[h5_cols].copy()
    result = result.set_index(["datetime", "instrument"])
    result = result.sort_index()

    return result


def save_h5(df: pd.DataFrame, path: Path):
    """保存为 H5 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    log.info("Writing H5: %s", path)
    t0 = time.time()
    df.to_hdf(str(path), key="data", mode="w")
    elapsed = time.time() - t0

    symbols = df.index.get_level_values("instrument").nunique()
    dates = df.index.get_level_values("datetime")
    log.info(
        "H5 saved: %d rows, %d symbols, %s ~ %s (%.1fMB, %.1fs)",
        len(df), symbols, dates.min().date(), dates.max().date(),
        path.stat().st_size / 1024 / 1024, elapsed,
    )


def convert_to_qlib(h5_path: Path, output_dir: Path):
    """将 H5 转换为 Qlib bin 格式。"""
    log.info("Converting to Qlib format: %s", output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_hdf(str(h5_path), key="data")

    cal_dir = output_dir / "calendars"
    feat_dir = output_dir / "features"
    inst_dir = output_dir / "instruments"
    cal_dir.mkdir(exist_ok=True)
    feat_dir.mkdir(exist_ok=True)
    inst_dir.mkdir(exist_ok=True)

    dates = df.index.get_level_values("datetime").unique().sort_values()
    with open(cal_dir / "day.txt", "w") as f:
        for d in dates:
            f.write(d.strftime("%Y-%m-%d") + "\n")

    instruments = df.index.get_level_values("instrument").unique().sort_values()
    with open(inst_dir / "all.txt", "w") as f:
        start_str = dates.min().strftime("%Y-%m-%d")
        end_str = dates.max().strftime("%Y-%m-%d")
        for inst in instruments:
            f.write(f"{inst}\t{start_str}\t{end_str}\n")

    col_map = {col: col.lstrip("$") for col in df.columns}
    t0 = time.time()
    total = len(instruments)
    for idx, inst in enumerate(instruments):
        inst_dir_path = feat_dir / inst.lower()
        inst_dir_path.mkdir(exist_ok=True)
        try:
            inst_data = df.xs(inst, level="instrument")
        except KeyError:
            continue
        # Deduplicate dates (keep last)
        inst_data = inst_data[~inst_data.index.duplicated(keep="last")]
        for orig_col, clean_col in col_map.items():
            if orig_col not in inst_data.columns:
                continue
            series = inst_data[orig_col].reindex(dates)
            bin_path = inst_dir_path / f"{clean_col}.day.bin"
            series.values.astype("float32").tofile(str(bin_path))

        if (idx + 1) % 500 == 0:
            log.info("  Qlib progress: %d / %d instruments", idx + 1, total)

    log.info(
        "Qlib format done: %d instruments, %d dates (%.1fs)",
        len(instruments), len(dates), time.time() - t0,
    )


def main():
    parser = argparse.ArgumentParser(description="Rebuild HK H5 from PostgreSQL")
    parser.add_argument("--qlib", action="store_true", help="Also generate Qlib bin format")
    args = parser.parse_args()

    engine = get_engine()

    # Load from DB
    df = load_from_db(engine)
    log.info("DB data: %d rows, %d symbols", len(df), df["symbol"].nunique())

    # Convert to H5 format
    h5_df = convert_to_h5_format(df)

    # Save H5
    save_h5(h5_df, H5_PATH)

    # Optionally convert to Qlib
    if args.qlib:
        convert_to_qlib(H5_PATH, QLIB_DIR)

    log.info("=== Done ===")


if __name__ == "__main__":
    main()
