"""
Qlib baostock 数据 → stock_daily_latest 转换脚本

读取 Qlib 二进制格式的 A 股日线数据，导入到 stock_daily_latest 表。
Qlib 存储的是前复权价格，直接导入即可（adj_factor=1.0）。

用法:
    python qlib_to_db.py                    # 导入所有股票
    python qlib_to_db.py --symbols 600519.SH 000001.SZ  # 导入指定股票
"""

import asyncio
import struct
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

# 优先使用容器内的 Qlib 数据，其次用主机的
_CANDIDATES = [
    "/app/db/qlib_data",  # Docker 容器内
    os.path.expanduser("~/.qlib/qlib_data/cn_data_baostock"),  # 主机
]
QLIB_BASE = next((p for p in _CANDIDATES if os.path.exists(p) and os.path.isdir(f"{p}/features")), _CANDIDATES[0])

# 数据库连接：容器内用 db:5432，主机用 localhost:5432
if os.path.exists("/app"):
    DB_URL = "postgresql+asyncpg://quantmind:quantmind2026@db:5432/quantmind"
else:
    DB_URL = "postgresql+asyncpg://quantmind:quantmind2026@localhost:5432/quantmind"


def read_qlib_bin(path: str) -> list[float] | None:
    """读取 Qlib 二进制特征文件，返回 float32 数组。"""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        data = f.read()
    n = len(data) // 4
    if n == 0:
        return []
    return list(struct.unpack(f"{n}f", data[: n * 4]))


def qlib_symbol_to_standard(sym: str) -> str:
    """sh600519 → 600519.SH, sz000001 → 000001.SZ"""
    if sym.startswith("sh"):
        return f"{sym[2:]}.SH"
    elif sym.startswith("sz"):
        return f"{sym[2:]}.SZ"
    elif sym.startswith("bj"):
        return f"{sym[2:]}.BJ"
    return sym


def standard_to_qlib(sym: str) -> str:
    """600519.SH → sh600519, 000001.SZ → sz000001"""
    s = sym.upper()
    if s.endswith(".SH"):
        return f"sh{s[:-3]}"
    elif s.endswith(".SZ"):
        return f"sz{s[:-3]}"
    elif s.endswith(".BJ"):
        return f"bj{s[:-3]}"
    return s.lower()


def load_qlib_stock(sym_dir: str, dates: list[str]) -> pd.DataFrame | None:
    """加载单只股票的 Qlib 数据，返回 DataFrame。

    Qlib 二进制格式:
    - Index 0: 占位符 (0.0)
    - Index 1 ~ N: 实际前复权价格
    - dates[i] 对应 data[i+1]
    """
    close = read_qlib_bin(f"{sym_dir}/close.day.bin")
    if not close or len(close) < 2:
        return None

    open_ = read_qlib_bin(f"{sym_dir}/open.day.bin")
    high = read_qlib_bin(f"{sym_dir}/high.day.bin")
    low = read_qlib_bin(f"{sym_dir}/low.day.bin")
    volume = read_qlib_bin(f"{sym_dir}/volume.day.bin")
    factor = read_qlib_bin(f"{sym_dir}/factor.day.bin")

    # Skip index 0 (placeholder), data starts at index 1
    # dates[i] corresponds to data[i+1]
    n = min(len(dates), len(close) - 1)
    if n <= 0:
        return None

    df = pd.DataFrame({
        "trade_date": dates[:n],
        "open": open_[1: n + 1] if open_ and len(open_) > n else close[1: n + 1],
        "high": high[1: n + 1] if high and len(high) > n else close[1: n + 1],
        "low": low[1: n + 1] if low and len(low) > n else close[1: n + 1],
        "close": close[1: n + 1],
        "volume": volume[1: n + 1] if volume and len(volume) > n else [0] * n,
        "adj_factor": factor[1: n + 1] if factor and len(factor) > n else [1.0] * n,
    })

    # 过滤无效数据（close=0）
    df = df[df["close"] > 0].copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

    return df


async def import_qlib_to_db(symbols: list[str] | None = None, since: str = "2026-01-01"):
    """将 Qlib 数据导入 stock_daily_latest。"""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    # Load calendar
    cal_path = f"{QLIB_BASE}/calendars/day.txt"
    with open(cal_path) as f:
        dates = [l.strip() for l in f if l.strip()]

    # List stocks
    feat_dir = f"{QLIB_BASE}/features"
    all_stocks = sorted(os.listdir(feat_dir))

    if symbols:
        qlib_syms = {standard_to_qlib(s) for s in symbols}
        all_stocks = [s for s in all_stocks if s in qlib_syms]

    since_date = pd.Timestamp(since).date()
    print(f"准备导入 {len(all_stocks)} 只股票，起始日期: {since}")
    print(f"Qlib 日期范围: {dates[0]} ~ {dates[-1]}")

    engine = create_async_engine(DB_URL, pool_size=5)

    total_rows = 0
    errors = 0
    imported = 0

    for i, sym in enumerate(all_stocks):
        sym_dir = f"{feat_dir}/{sym}"
        if not os.path.isdir(sym_dir):
            continue

        df = load_qlib_stock(sym_dir, dates)
        if df is None or df.empty:
            continue

        std_sym = qlib_symbol_to_standard(sym)
        df["symbol"] = std_sym

        # 过滤日期
        df = df[df["trade_date"] >= since_date]
        if df.empty:
            continue

        # 批量 upsert
        try:
            async with engine.begin() as conn:
                for _, row in df.iterrows():
                    await conn.execute(text("""
                        INSERT INTO stock_daily_latest (symbol, trade_date, open, high, low, close, volume, adj_factor)
                        VALUES (:symbol, :trade_date, :open, :high, :low, :close, :volume, 1.0)
                        ON CONFLICT (symbol, trade_date) DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            adj_factor = 1.0
                    """), {
                        "symbol": std_sym,
                        "trade_date": row["trade_date"],
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row["volume"]),
                    })
            total_rows += len(df)
            imported += 1
        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"  [ERROR] {std_sym}: {e}")

        if (i + 1) % 200 == 0:
            print(f"  进度: {i+1}/{len(all_stocks)}, 已导入 {imported} 只 {total_rows} 行, 错误 {errors}")

    await engine.dispose()
    print(f"\n完成: 导入 {imported} 只股票, {total_rows} 行, {errors} 个错误")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Import Qlib data to stock_daily_latest")
    parser.add_argument("--symbols", nargs="*", help="Specific symbols (e.g., 600519.SH 000001.SZ)")
    parser.add_argument("--since", default="2026-01-01", help="Import data since this date")
    args = parser.parse_args()

    asyncio.run(import_qlib_to_db(symbols=args.symbols, since=args.since))
