"""港股数据管线 — yfinance 下载 → H5 → Qlib 格式

恒生指数 + 恒生科技指数成分股，约 82 只股票。
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# 恒生指数 (HSI) 成分股 — 主要蓝筹
HSI_CONSTITUENTS = [
    "0001.HK",  # 长和
    "0002.HK",  # 中电控股
    "0003.HK",  # 中华煤气
    "0005.HK",  # 汇丰控股
    "0006.HK",  # 电能实业
    "0011.HK",  # 恒生银行
    "0012.HK",  # 恒基地产
    "0016.HK",  # 新鸿基地产
    "0017.HK",  # 新世界发展
    "0027.HK",  # 银河娱乐
    "0066.HK",  # 港铁公司
    "0101.HK",  # 恒隆集团
    "0175.HK",  # 吉利汽车
    "0241.HK",  # 阿里健康
    "0267.HK",  # 中信股份
    "0288.HK",  # 万洲国际
    "0316.HK",  # 东方海外国际
    "0322.HK",  # 康师傅控股
    "0386.HK",  # 中国石化
    "0388.HK",  # 香港交易所
    "0669.HK",  # 创科实业
    "0700.HK",  # 腾讯控股
    "0762.HK",  # 中国联通
    "0823.HK",  # 领展房产
    "0857.HK",  # 中国石油
    "0868.HK",  # 信义玻璃
    "0881.HK",  # 中升控股
    "0883.HK",  # 中国海洋石油
    "0939.HK",  # 建设银行
    "0941.HK",  # 中国移动
    "0960.HK",  # 龙湖集团
    "0968.HK",  # 信义光能
    "0981.HK",  # 中芯国际
    "1024.HK",  # 快手
    "1038.HK",  # 长江基建
    "1044.HK",  # 恒安国际
    "1093.HK",  # 石药集团
    "1109.HK",  # 华润置地
    "1113.HK",  # 长实集团
    "1177.HK",  # 中国生物制药
    "1211.HK",  # 比亚迪
    "1299.HK",  # 友邦保险
    "1378.HK",  # 中国宏桥
    "1398.HK",  # 工商银行
    "1810.HK",  # 小米集团
    "1876.HK",  # 百威亚太
    "1928.HK",  # 金沙中国
    "1929.HK",  # 周大福
    "1997.HK",  # 九龙仓置业
    "2007.HK",  # 碧桂园
    "2018.HK",  # 瑞声科技
    "2020.HK",  # 安踏体育
    "2269.HK",  # 药明生物
    "2313.HK",  # 申洲国际
    "2318.HK",  # 中国平安
    "2319.HK",  # 蒙牛乳业
    "2382.HK",  # 舜宇光学
    "2388.HK",  # 中银香港
    "2628.HK",  # 中国人寿
    "2688.HK",  # 新奥能源
    "3328.HK",  # 交通银行
    "3690.HK",  # 美团
    "3968.HK",  # 招商银行
    "3988.HK",  # 中国银行
    "6098.HK",  # 碧桂园服务
    "6618.HK",  # 京东健康
    "6862.HK",  # 海底捞
    "9618.HK",  # 京东集团
    "9626.HK",  # 哔哩哔哩
    "9633.HK",  # 农夫山泉
    "9888.HK",  # 百度集团
    "9961.HK",  # 携程集团
    "9988.HK",  # 阿里巴巴
    "9999.HK",  # 网易
]

# 恒生科技指数 (HSTECH) 额外成分股
HSTECH_EXTRA = [
    "0268.HK",  # 金蝶国际
    "0772.HK",  # 阅文集团
    "0909.HK",  # 明源云
    "1833.HK",  # 平安好医生
    "2015.HK",  # 理想汽车
    "2518.HK",  # 汽车之家
    "6690.HK",  # 海尔智家
    "9868.HK",  # 小鹏汽车
    "9866.HK",  # 蔚来
]

# 合并去重
HK_SYMBOLS = sorted(set(HSI_CONSTITUENTS + HSTECH_EXTRA))


def download_yfinance_batch(
    symbols: list[str],
    start_date: str = "2020-01-01",
    end_date: str | None = None,
    batch_size: int = 20,
) -> pd.DataFrame:
    """使用 yfinance 批量下载股票数据"""
    import yfinance as yf

    all_dfs = []
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        logger.info("  Downloading batch %d/%d: %s...", i // batch_size + 1, (len(symbols) + batch_size - 1) // batch_size, batch[:3])

        try:
            df = yf.download(
                batch,
                start=start_date,
                end=end_date,
                group_by="ticker",
                progress=False,
                auto_adjust=True,
            )

            if df.empty:
                logger.warning("  Batch returned empty")
                continue

            # Reshape: (date, ticker*field) → (date, instrument) with OHLCV
            for symbol in batch:
                try:
                    if len(batch) == 1:
                        ticker_df = df.copy()
                    else:
                        ticker_df = df[symbol].copy()

                    ticker_df = ticker_df.dropna(subset=["Close"])
                    if ticker_df.empty:
                        continue

                    ticker_df = ticker_df[["Open", "High", "Low", "Close", "Volume"]].copy()
                    ticker_df.columns = ["open", "high", "low", "close", "volume"]
                    ticker_df["instrument"] = symbol.replace(".HK", "")
                    ticker_df.index.name = "datetime"
                    ticker_df = ticker_df.reset_index()
                    all_dfs.append(ticker_df)
                except Exception as e:
                    logger.debug("  Skip %s: %s", symbol, e)

        except Exception as e:
            logger.error("  Batch download failed: %s", e)

        time.sleep(1)  # Rate limiting

    if not all_dfs:
        return pd.DataFrame()

    return pd.concat(all_dfs, ignore_index=True)


def download_all_hk(
    symbols: list[str] | None = None,
    start_date: str = "2020-01-01",
    end_date: str | None = None,
    output_dir: str = "/app/db/hk_data",
) -> str:
    """下载所有港股数据并保存为 H5"""
    symbols = symbols or HK_SYMBOLS
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading %d HK stocks from yfinance...", len(symbols))

    df = download_yfinance_batch(symbols, start_date=start_date, end_date=end_date)

    if df.empty:
        raise RuntimeError("No HK data downloaded")

    # 添加复权因子列（港股需要复权，但 yfinance auto_adjust=True 已处理）
    df["factor"] = 1.0

    # 使用 $ 前缀列名（RD-Agent 兼容）
    df = df.rename(columns={
        "open": "$open",
        "high": "$high",
        "low": "$low",
        "close": "$close",
        "volume": "$volume",
        "factor": "$factor",
    })
    df = df[["datetime", "instrument", "$open", "$high", "$low", "$close", "$volume", "$factor"]]
    df = df.set_index(["datetime", "instrument"])
    df = df.sort_index()

    h5_path = output_path / "daily_pv.h5"
    df.to_hdf(str(h5_path), key="data", mode="w")
    logger.info("Saved H5: %s (%d rows, %d symbols)", h5_path, len(df), df.index.get_level_values("instrument").nunique())

    return str(h5_path)


def convert_h5_to_qlib_format(
    h5_path: str,
    output_dir: str = "/app/db/qlib_data/hk_data",
) -> str:
    """将 H5 转换为 Qlib 原生 bin 格式"""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    df = pd.read_hdf(h5_path, key="data")

    cal_dir = output / "calendars"
    feat_dir = output / "features"
    inst_dir = output / "instruments"
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
            bin_path = inst_dir_path / f"{clean_col}.day.bin"
            series.values.astype("float32").tofile(str(bin_path))

    logger.info("Converted to Qlib format: %s (%d instruments, %d dates)", output, len(instruments), len(dates))
    return str(output)


def is_hk_data_ready(qlib_dir: str = "/app/db/qlib_data/hk_data") -> bool:
    """检查港股数据是否已就绪"""
    p = Path(qlib_dir)
    return (
        p.is_dir()
        and (p / "calendars" / "day.txt").is_file()
        and (p / "instruments" / "all.txt").is_file()
        and (p / "features").is_dir()
        and len(list((p / "features").iterdir())) > 0
    )
