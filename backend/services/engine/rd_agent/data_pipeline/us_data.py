"""美股数据管线 — yfinance 下载 → H5 → Qlib 格式

S&P 500 精选 + NASDAQ 100 科技股，约 100 只股票。
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# S&P 500 完整列表 (约500只)
SP500_FULL = [
    "A","AAL","AAPL","ABBV","ABT","ACN","ADBE","ADI","ADM","ADP","ADSK","AEE","AEP","AES","AFL","AIG","AIZ","AJG","AKAM","ALB","ALGN","ALK","ALL","ALLE","AMAT","AMCR","AMD","AME","AMGN","AMP","AMT","AMZN","ANET","ANSS","AON","AOS","APA","APD","APH","APTV","ARE","ATO","ATVI","AVB","AVGO","AVY","AWK","AXP","AZO",
    "BA","BAC","BAX","BBWI","BBY","BDX","BEN","BF.B","BIO","BIIB","BK","BKNG","BKR","BMY","BR","BRK.B","BRO","BSX","BWA","BXP",
    "C","CAG","CAH","CARR","CAT","CB","CBOE","CBRE","CCI","CCL","CDAY","CDNS","CDW","CE","CEG","CF","CFG","CHD","CHRW","CHTR","CI","CINF","CL","CLX","CMA","CMCSA","CME","CMG","CMI","CMS","CNC","CNP","COF","COO","COP","COST","CPB","CPRT","CPT","CRL","CRM","CRWD","CSCO","CSGP","CSX","CTAS","CTLT","CTRA","CTSH","CTVA","CVS","CVX","CZR",
    "D","DAL","DD","DE","DFS","DG","DGX","DHI","DHR","DIS","DISH","DLTR","DOV","DOW","DPZ","DRI","DTE","DUK","DVA","DVN","DXC","DXCM",
    "EA","EBAY","ECL","ED","EFX","EIX","EL","EMN","EMR","ENPH","EOG","EPAM","EQIX","EQR","EQT","ES","ESS","ETN","ETR","ETSY","EVRG","EW","EXC","EXPD","EXPE","EXR",
    "F","FANG","FAST","FBHS","FCX","FDS","FDX","FE","FFIV","FIS","FISV","FLT","FMC","FOX","FOXA","FRC","FRT","FTNT","FTV",
    "GD","GE","GILD","GIS","GL","GLW","GM","GNRC","GOOG","GOOGL","GPC","GPN","GRMN","GS","GWW",
    "HAL","HAS","HBAN","HCA","HD","HOLX","HON","HPE","HPQ","HRL","HSIC","HST","HSY","HUM","HWM",
    "IBM","ICE","IDXX","IEX","IFF","ILMN","INCY","INTC","INTU","INVH","IP","IPG","IQV","IR","IRM","ISRG","IT","ITW","IVZ",
    "J","JBHT","JCI","JKHY","JNJ","JNPR","JPM","K","KDP","KEY","KEYS","KHC","KIM","KLAC","KMB","KMI","KMX","KO","KR",
    "L","LDOS","LEN","LH","LHX","LIN","LKQ","LLY","LMT","LNC","LNT","LOW","LRCX","LUMN","LUV","LVS","LW","LYB","LYV",
    "MA","MAA","MAR","MAS","MCD","MCHP","MCK","MCO","MDLZ","MDT","MET","META","MGM","MHK","MKC","MKTX","MLM","MMC","MMM","MNST","MO","MOH","MOS","MPC","MPWR","MRK","MRNA","MRO","MS","MSCI","MSFT","MSI","MTB","MTCH","MTD","MU",
    "NCLH","NDAQ","NDSN","NEE","NEM","NFLX","NI","NKE","NOC","NOW","NRG","NSC","NTAP","NTRS","NUE","NVDA","NVR","NWL","NWS","NWSA",
    "ODFL","OGN","OKE","OMC","ON","ORCL","ORLY","OTIS","OXY",
    "PARA","PAYC","PAYX","PCAR","PCG","PEAK","PEG","PEP","PFE","PFG","PG","PGR","PH","PHM","PKG","PKI","PLD","PLTR","PM","PNC","PNR","PNW","POOL","PPG","PPL","PRU","PSA","PSX","PTC","PVH","PWR","PXD","PYPL",
    "QCOM","QRVO",
    "RCL","RE","REG","REGN","RF","RHI","RJF","RL","RMD","ROK","ROL","ROP","ROST","RSG","RTX",
    "SBAC","SBNY","SBUX","SCHW","SEE","SHW","SIVB","SJM","SLB","SNA","SNPS","SO","SPG","SPGI","SRE","STE","STT","STX","STZ","SWK","SWKS","SYF","SYK","SYY",
    "T","TAP","TDG","TDY","TECH","TEL","TER","TFC","TFX","TGT","TMO","TMUS","TPR","TRGP","TRMB","TROW","TRV","TSCO","TSLA","TSN","TT","TTWO","TXN","TXT","TYL",
    "UAL","UDR","UHS","ULTA","UNH","UNP","UPS","URI","USB",
    "V","VFC","VICI","VLO","VMC","VNO","VRSK","VRSN","VRTX","VTR","VTRS","VZ",
    "WAB","WAT","WBA","WBD","WDC","WEC","WELL","WFC","WHR","WM","WMB","WMT","WRB","WRK","WST","WTW","WY","WYNN",
    "XEL","XOM","XRAY","XYL",
    "YUM","ZBH","ZBRA","ZION","ZS",
]

# NASDAQ 100 额外科技股（不在 S&P 500 中的）
NASDAQ_EXTRA = [
    "ASML","PANW","WDAY","DDOG","CRWD","NET","SNOW",
    "COIN","ABNB","DASH","UBER","LYFT","PINS","SNAP","SPOT",
    "SHOP","SOFI","HOOD",
    "ARM","SMCI","MRVL","WDC",
    "MELI","SE","PDD","JD","BIDU","NIO","XPEV","LI",
]

# 合并去重
US_SYMBOLS = sorted(set(SP500_FULL + NASDAQ_EXTRA))


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
                    ticker_df["instrument"] = symbol
                    ticker_df.index.name = "datetime"
                    ticker_df = ticker_df.reset_index()
                    all_dfs.append(ticker_df)
                except Exception as e:
                    logger.debug("  Skip %s: %s", symbol, e)

        except Exception as e:
            logger.error("  Batch download failed: %s", e)

        time.sleep(1)

    if not all_dfs:
        return pd.DataFrame()

    return pd.concat(all_dfs, ignore_index=True)


def download_all_us(
    symbols: list[str] | None = None,
    start_date: str = "2020-01-01",
    end_date: str | None = None,
    output_dir: str = "/app/db/us_data",
) -> str:
    """下载所有美股数据并保存为 H5"""
    symbols = symbols or US_SYMBOLS
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading %d US stocks from yfinance...", len(symbols))

    df = download_yfinance_batch(symbols, start_date=start_date, end_date=end_date)

    if df.empty:
        raise RuntimeError("No US data downloaded")

    df["factor"] = 1.0

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
    output_dir: str = "/app/db/qlib_data/us_data",
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


def is_us_data_ready(qlib_dir: str = "/app/db/qlib_data/us_data") -> bool:
    """检查美股数据是否已就绪"""
    p = Path(qlib_dir)
    return (
        p.is_dir()
        and (p / "calendars" / "day.txt").is_file()
        and (p / "instruments" / "all.txt").is_file()
        and (p / "features").is_dir()
        and len(list((p / "features").iterdir())) > 0
    )
