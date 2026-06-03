"""加密货币数据管线 — Binance 公开 API 下载 → H5 → Qlib 格式

使用 data-api.binance.vision（无需翻墙）下载数据。
支持两种时间粒度:
- 日线 (1d): 用于 RD-Agent 因子挖掘, 2010 年至今
- 5分钟 (5m): 用于短线分析, 最近 90 天
生成 RD-Agent 兼容的 daily_pv.h5（$前缀列名）和 Qlib bin 格式。
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Binance K线 API（按优先级排序，第一个可用的会被使用）
BINANCE_KLINE_URLS = [
    "https://data-api.binance.vision/api/v3/klines",
    "https://api.binance.com/api/v3/klines",
    "https://api1.binance.com/api/v3/klines",
]

# 默认交易对 (top-35 by volume)
DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "MATICUSDT", "LTCUSDT", "UNIUSDT", "ATOMUSDT", "ETCUSDT",
    "FILUSDT", "APTUSDT", "NEARUSDT", "ARBUSDT", "OPUSDT",
    "MKRUSDT", "AAVEUSDT", "GRTUSDT", "INJUSDT", "SEIUSDT",
    "TIAUSDT", "SUIUSDT", "RUNEUSDT", "FETUSDT", "RENDERUSDT",
    "PEPEUSDT", "SHIBUSDT", "FLOKIUSDT", "WIFUSDT", "BONKUSDT",
]

# 找到第一个可用的 API endpoint
_working_url: str | None = None


def _get_api_url() -> str:
    """返回可用的 Binance API URL（首次调用时探测）"""
    global _working_url
    if _working_url:
        return _working_url

    import requests
    for url in BINANCE_KLINE_URLS:
        try:
            r = requests.get(url, params={"symbol": "BTCUSDT", "interval": "1d", "limit": 1}, timeout=10)
            if r.status_code == 200:
                _working_url = url
                logger.info("Using Binance API: %s", url)
                return url
        except Exception:
            continue

    _working_url = BINANCE_KLINE_URLS[0]
    logger.warning("No Binance API tested OK, using default: %s", _working_url)
    return _working_url


def download_binance_klines(
    symbol: str,
    interval: str = "1d",
    start_date: str = "2010-01-01",
    end_date: str | None = None,
    limit: int = 1000,
) -> pd.DataFrame:
    """从 Binance 公开 API 下载 K 线数据"""
    import requests

    api_url = _get_api_url()
    start_ms = int(pd.Timestamp(start_date).timestamp() * 1000)
    end_ms = int(pd.Timestamp(end_date).timestamp() * 1000) if end_date else int(time.time() * 1000)

    all_data = []
    current_start = start_ms
    request_count = 0

    while current_start < end_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "endTime": end_ms,
            "limit": limit,
        }
        try:
            resp = requests.get(api_url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("  %s request failed: %s, retrying...", symbol, e)
            time.sleep(2)
            continue

        if not data:
            break

        all_data.extend(data)
        current_start = data[-1][6] + 1  # close_time + 1
        request_count += 1

        # Rate limiting: 5min data needs more requests, be gentle
        time.sleep(0.15)

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
    start_date: str = "2010-01-01",
    end_date: str | None = None,
    output_dir: str = "/app/db/crypto_data",
    interval: str = "1d",
) -> str:
    """下载所有交易对数据并保存为 H5

    Args:
        interval: K线周期, "1d" (日线) 或 "5m" (5分钟)
    Returns: H5 文件路径
    """
    symbols = symbols or DEFAULT_SYMBOLS
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 5min 数据使用单独的子目录
    if interval == "5m":
        csv_dir = output_path / "csv_5m"
        h5_name = "5min_pv.h5"
    else:
        csv_dir = output_path / "csv"
        h5_name = "daily_pv.h5"
    csv_dir.mkdir(exist_ok=True)

    logger.info("Downloading %d crypto symbols (%s) from Binance...", len(symbols), interval)

    all_dfs = []
    for i, symbol in enumerate(symbols, 1):
        csv_file = csv_dir / f"{symbol}.csv"
        if csv_file.exists():
            logger.info("  [%d/%d] %s — cached", i, len(symbols), symbol)
            df = pd.read_csv(csv_file, parse_dates=["datetime"])
        else:
            logger.info("  [%d/%d] %s — downloading...", i, len(symbols), symbol)
            try:
                df = download_binance_klines(symbol, interval=interval, start_date=start_date, end_date=end_date)
                if df.empty:
                    logger.warning("  [%d/%d] %s — no data", i, len(symbols), symbol)
                    continue
                df.to_csv(csv_file, index=False)
            except Exception as e:
                logger.error("  [%d/%d] %s — failed: %s", i, len(symbols), symbol, e)
                continue

        all_dfs.append(df)

    if not all_dfs:
        raise RuntimeError("No data downloaded")

    # 合并为 H5（使用 $ 前缀列名，与 RD-Agent daily_pv.h5 兼容）
    combined = pd.concat(all_dfs, ignore_index=True)
    combined["factor"] = 1.0
    combined = combined.rename(columns={
        "open": "$open",
        "high": "$high",
        "low": "$low",
        "close": "$close",
        "volume": "$volume",
        "factor": "$factor",
    })
    combined = combined[["datetime", "instrument", "$open", "$high", "$low", "$close", "$volume", "$factor"]]
    combined = combined.set_index(["datetime", "instrument"])
    combined = combined.sort_index()

    h5_path = output_path / h5_name
    combined.to_hdf(str(h5_path), key="data", mode="w")
    logger.info("Saved H5: %s (%d rows, %d symbols)", h5_path, len(combined), len(all_dfs))

    return str(h5_path)


def convert_h5_to_qlib_format(
    h5_path: str,
    output_dir: str = "/app/db/qlib_data/crypto_data",
    freq: str = "day",
) -> str:
    """将 H5 转换为 Qlib 原生 bin 格式

    Args:
        freq: "day" 或 "5min"
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    df = pd.read_hdf(h5_path, key="data")

    cal_dir = output / "calendars"
    feat_dir = output / "features"
    inst_dir = output / "instruments"
    cal_dir.mkdir(exist_ok=True)
    feat_dir.mkdir(exist_ok=True)
    inst_dir.mkdir(exist_ok=True)

    # 日历
    dates = df.index.get_level_values("datetime").unique().sort_values()
    cal_file = f"{freq}.txt"
    with open(cal_dir / cal_file, "w") as f:
        for d in dates:
            if freq == "5min":
                f.write(d.strftime("%Y-%m-%d %H:%M:%S") + "\n")
            else:
                f.write(d.strftime("%Y-%m-%d") + "\n")

    # 标的列表
    instruments = df.index.get_level_values("instrument").unique().sort_values()
    inst_file = "all.txt"
    with open(inst_dir / inst_file, "w") as f:
        start_str = dates.min().strftime("%Y-%m-%d")
        end_str = dates.max().strftime("%Y-%m-%d")
        for inst in instruments:
            f.write(f"{inst}\t{start_str}\t{end_str}\n")

    # 特征数据
    col_map = {col: col.lstrip("$") for col in df.columns}
    bin_suffix = f"{freq}.bin" if freq == "5min" else f"{freq}.bin"
    for inst in instruments:
        inst_dir_path = feat_dir / inst.lower()
        inst_dir_path.mkdir(exist_ok=True)
        try:
            inst_data = df.xs(inst, level="instrument")
        except KeyError:
            continue
        for orig_col, clean_col in col_map.items():
            if orig_col not in inst_data.columns:
                continue
            series = inst_data[orig_col].reindex(dates)
            bin_path = inst_dir_path / f"{clean_col}.{bin_suffix}"
            series.values.astype("float32").tofile(str(bin_path))

    logger.info("Converted to Qlib format: %s (%d instruments, %d dates, freq=%s)", output, len(instruments), len(dates), freq)
    return str(output)


def is_crypto_data_ready(qlib_dir: str = "/app/db/qlib_data/crypto_data") -> bool:
    """检查加密货币数据是否已就绪 (支持 5min 和 day 两种频率)"""
    p = Path(qlib_dir)
    has_calendar = (p / "calendars" / "5min.txt").is_file() or (p / "calendars" / "day.txt").is_file()
    return (
        p.is_dir()
        and has_calendar
        and (p / "instruments" / "all.txt").is_file()
        and (p / "features").is_dir()
        and len(list((p / "features").iterdir())) > 0
    )
