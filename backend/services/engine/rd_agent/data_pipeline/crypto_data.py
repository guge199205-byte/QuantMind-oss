"""加密货币数据管线 — Binance 公开 API 下载 → H5 → Qlib 格式"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Binance 公开 K线 API
BINANCE_KLINE_URL = "https://api.binance.com/api/v3/klines"

# 默认交易对 (top-100 by volume)
DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "MATICUSDT", "LTCUSDT", "UNIUSDT", "ATOMUSDT", "ETCUSDT",
    "FILUSDT", "APTUSDT", "NEARUSDT", "ARBUSDT", "OPUSDT",
    "MKRUSDT", "AAVEUSDT", "GRTUSDT", "INJUSDT", "SEIUSDT",
    "TIAUSDT", "SUIUSDT", "RUNEUSDT", "FETUSDT", "RENDERUSDT",
    "PEPEUSDT", "SHIBUSDT", "FLOKIUSDT", "WIFUSDT", "BONKUSDT",
]


def download_binance_klines(
    symbol: str,
    interval: str = "1d",
    start_date: str = "2024-01-01",
    end_date: str | None = None,
    limit: int = 1000,
) -> pd.DataFrame:
    """从 Binance 公开 API 下载 K 线数据"""
    import requests

    start_ms = int(pd.Timestamp(start_date).timestamp() * 1000)
    end_ms = int(pd.Timestamp(end_date).timestamp() * 1000) if end_date else int(time.time() * 1000)

    all_data = []
    current_start = start_ms

    while current_start < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "endTime": end_ms,
            "limit": limit,
        }
        resp = requests.get(BINANCE_KLINE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if not data:
            break

        all_data.extend(data)
        current_start = data[-1][6] + 1  # close_time + 1

        # Rate limiting
        time.sleep(0.2)

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_volume",
        "taker_buy_quote_volume", "ignore",
    ])

    df["datetime"] = pd.to_datetime(df["open_time"], unit="ms")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    df = df[["datetime", "open", "high", "low", "close", "volume"]]
    df["instrument"] = symbol
    return df


def download_all_crypto(
    symbols: list[str] | None = None,
    start_date: str = "2024-01-01",
    end_date: str | None = None,
    output_dir: str = "/app/db/crypto_data",
) -> str:
    """下载所有交易对数据并保存为 H5"""
    symbols = symbols or DEFAULT_SYMBOLS
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    csv_dir = output_path / "csv"
    csv_dir.mkdir(exist_ok=True)

    logger.info("Downloading %d crypto symbols from Binance...", len(symbols))

    all_dfs = []
    for i, symbol in enumerate(symbols, 1):
        csv_file = csv_dir / f"{symbol}.csv"
        if csv_file.exists():
            logger.info("  [%d/%d] %s — cached", i, len(symbols), symbol)
            df = pd.read_csv(csv_file, parse_dates=["datetime"])
        else:
            logger.info("  [%d/%d] %s — downloading...", i, len(symbols), symbol)
            try:
                df = download_binance_klines(symbol, start_date=start_date, end_date=end_date)
                if df.empty:
                    logger.warning("  [%d/%d] %s — no data", i, len(symbols), symbol)
                    continue
                df.to_csv(csv_dir / f"{symbol}.csv", index=False)
            except Exception as e:
                logger.error("  [%d/%d] %s — failed: %s", i, len(symbols), symbol, e)
                continue

        all_dfs.append(df)

    if not all_dfs:
        raise RuntimeError("No data downloaded")

    # 合并为 H5
    combined = pd.concat(all_dfs, ignore_index=True)
    combined["factor"] = 1.0  # 加密货币无复权
    combined = combined.set_index(["datetime", "instrument"])
    combined = combined.sort_index()

    h5_path = output_path / "daily_pv.h5"
    combined.to_hdf(str(h5_path), key="data", mode="w")
    logger.info("Saved H5: %s (%d rows, %d symbols)", h5_path, len(combined), len(all_dfs))

    return str(h5_path)


def convert_h5_to_qlib_format(
    h5_path: str,
    output_dir: str = "/app/db/qlib_data/crypto_data",
) -> str:
    """将 H5 转换为 Qlib 原生 bin 格式"""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    df = pd.read_hdf(h5_path, key="data")

    # Qlib 目录结构
    cal_dir = output / "calendars"
    feat_dir = output / "features"
    inst_dir = output / "instruments"
    cal_dir.mkdir(exist_ok=True)
    feat_dir.mkdir(exist_ok=True)
    inst_dir.mkdir(exist_ok=True)

    # 日历
    dates = df.index.get_level_values("datetime").unique().sort_values()
    with open(cal_dir / "day.txt", "w") as f:
        for d in dates:
            f.write(d.strftime("%Y-%m-%d") + "\n")

    # 标的列表
    instruments = df.index.get_level_values("instrument").unique().sort_values()
    with open(inst_dir / "all.txt", "w") as f:
        start_str = dates.min().strftime("%Y-%m-%d")
        end_str = dates.max().strftime("%Y-%m-%d")
        for inst in instruments:
            f.write(f"{inst}\t{start_str}\t{end_str}\n")

    # 特征数据 (bin 格式)
    fields = ["open", "high", "low", "close", "volume", "factor"]
    for inst in instruments:
        inst_dir_path = feat_dir / inst.lower()
        inst_dir_path.mkdir(exist_ok=True)

        try:
            inst_data = df.xs(inst, level="instrument")
        except KeyError:
            continue

        for field in fields:
            if field not in inst_data.columns:
                continue
            series = inst_data[field].reindex(dates)
            bin_path = inst_dir_path / f"{field}.day.bin"
            series.values.astype("float32").tofile(str(bin_path))

    logger.info("Converted to Qlib format: %s", output)
    return str(output)
