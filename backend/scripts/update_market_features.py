#!/usr/bin/env python3
"""多市场特征工程 — 从 H5 数据计算 OHLCV 特征并保存为 parquet。

支持加密货币、港股、美股市场。复用 update_feature_parquet.py 中的
compute_features_for_group() 计算纯 OHLCV 特征，跳过 A 股特有列。

用法:
    python update_market_features.py --market crypto
    python update_market_features.py --market hong_kong
    python update_market_features.py --market us_stock
    python update_market_features.py --market crypto --rebuild
    python update_market_features.py --market crypto --dry-run
"""

import argparse
import os
import sys
import warnings
from datetime import date, datetime
from pathlib import Path

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

# 容器内 vs 主机：优先用脚本位置推断，回退到 /app
_script_root = Path(__file__).resolve().parents[2]
if (_script_root / "db").is_dir():
    PROJECT_ROOT = _script_root
elif Path("/app/db").is_dir():
    PROJECT_ROOT = Path("/app")
else:
    PROJECT_ROOT = _script_root

FEATURE_SNAPSHOT_DIR = PROJECT_ROOT / "db" / "feature_snapshots"
FEATURE_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# 市场 → H5 文件路径映射
MARKET_H5_PATHS = {
    "crypto": PROJECT_ROOT / "db" / "crypto_data" / "5min_pv.h5",
    "hong_kong": PROJECT_ROOT / "db" / "hk_data" / "daily_pv.h5",
    "us_stock": PROJECT_ROOT / "db" / "us_data" / "daily_pv.h5",
}

# 市场 → 输出 parquet 文件名
MARKET_PARQUET_NAMES = {
    "crypto": "model_features_crypto.parquet",
    "hong_kong": "model_features_hk.parquet",
    "us_stock": "model_features_us.parquet",
}


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def _aggregate_crypto_to_daily(df: pd.DataFrame) -> pd.DataFrame:
    """将加密货币 5 分钟 K 线聚合为日线。"""
    _log(f"  聚合 5min → daily: {len(df):,} 行")

    agg_dict = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    # 可选列
    for col in ["amount"]:
        if col in df.columns:
            agg_dict[col] = "sum"

    grouped = df.groupby(["instrument", "trade_date"], as_index=False).agg(agg_dict)

    # 重算 amount（如果需要）
    if "amount" not in grouped.columns:
        grouped["amount"] = grouped["close"] * grouped["volume"]

    _log(f"  聚合后: {len(grouped):,} 行, {grouped['instrument'].nunique()} 个标的")
    return grouped


def load_h5_data(market: str) -> pd.DataFrame:
    """从 H5 文件加载数据，转换为 compute_features_for_group() 兼容格式。"""
    h5_path = MARKET_H5_PATHS.get(market)
    if not h5_path or not h5_path.exists():
        raise FileNotFoundError(f"H5 文件不存在: {h5_path}")

    _log(f"读取 H5: {h5_path}")
    df = pd.read_hdf(str(h5_path), key="data")

    # 重置索引，列名去掉 $ 前缀
    df = df.reset_index()
    col_map = {c: c.lstrip("$") for c in df.columns if c.startswith("$")}
    df = df.rename(columns=col_map)

    # 确保 datetime 列名统一
    if "datetime" in df.columns:
        df = df.rename(columns={"datetime": "trade_date"})
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

    # 加密货币 5 分钟数据需要聚合到日线
    if market == "crypto":
        df = _aggregate_crypto_to_daily(df)

    # 合成 amount（close * volume）
    if "amount" not in df.columns:
        df["amount"] = df["close"] * df["volume"]

    # adj_factor 默认 1.0
    if "adj_factor" not in df.columns:
        df["adj_factor"] = 1.0

    # turnover_rate 默认 0（compute_features_for_group 会重算）
    if "turnover_rate" not in df.columns:
        df["turnover_rate"] = 0.0

    # A 股特有列填 0
    a_share_cols = [
        "pe_ttm", "pb", "roe", "bp", "ep_ttm",
        "float_mv", "total_mv",
    ]
    for col in a_share_cols:
        if col not in df.columns:
            df[col] = 0.0

    # ln_mv_total 用 amount 近似
    if "ln_mv_total" not in df.columns:
        df["ln_mv_total"] = np.log(df["amount"].clip(lower=1))

    # 分类列
    for col in ["industry", "is_st", "listing_market"]:
        if col not in df.columns:
            df[col] = ""

    # 指数成分 / 概念标签
    index_concept_cols = [
        "idx_all", "idx_hs300", "idx_zz1000", "idx_chinext", "idx_margin",
        "concept_ai", "concept_chip", "concept_new_energy", "concept_pv",
        "concept_military", "concept_medical", "concept_fintech",
        "concept_consumption", "concept_state_owned", "concept_lithium",
    ]
    for col in index_concept_cols:
        if col not in df.columns:
            df[col] = 0

    # 技术指标列（DB 已有的，这里没有就填 NaN，compute_features_for_group 会重算）
    tech_cols = [
        "return_1d", "return_5d", "return_20d", "ma5", "ma20", "ma60",
        "rsi_14", "kdj_k", "macd_hist", "vol_std_20", "vol_atr_14",
        "beta_20", "flow_net_amount", "volume_ma_5", "amount_ma_5",
    ]
    for col in tech_cols:
        if col not in df.columns:
            df[col] = np.nan

    _log(f"  加载 {len(df):,} 行, {df['instrument'].nunique()} 个标的")
    _log(f"  日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")

    return df


def compute_market_features(df: pd.DataFrame, market: str) -> pd.DataFrame:
    """为所有标的计算特征。"""
    from backend.scripts.update_feature_parquet import compute_features_for_group

    instruments = df["instrument"].unique()
    total = len(instruments)
    _log(f"  计算特征（{total} 个标的）...")

    results = []
    for i, (sym, group) in enumerate(df.groupby("instrument"), 1):
        try:
            feat = compute_features_for_group(group)
            results.append(feat)
        except Exception as e:
            _log(f"    跳过 {sym}: {e}")
        if i % 50 == 0:
            _log(f"    进度: {i}/{total}")

    if not results:
        return pd.DataFrame()

    all_feat = pd.concat(results, ignore_index=True)

    # 清理 A 股特有列（保留但全为 0 的列可以删掉以减小文件）
    drop_cols = [
        "industry", "is_st", "listing_market",
        "idx_all", "idx_hs300", "idx_zz1000", "idx_chinext", "idx_margin",
        "concept_ai", "concept_chip", "concept_new_energy", "concept_pv",
        "concept_military", "concept_medical", "concept_fintech",
        "concept_consumption", "concept_state_owned", "concept_lithium",
    ]
    for col in drop_cols:
        if col in all_feat.columns and (all_feat[col] == 0).all():
            all_feat = all_feat.drop(columns=[col])

    return all_feat


def main():
    parser = argparse.ArgumentParser(description="多市场特征工程")
    parser.add_argument("--market", required=True, choices=["crypto", "hong_kong", "us_stock"],
                        help="市场: crypto, hong_kong, us_stock")
    parser.add_argument("--rebuild", action="store_true", help="重建全部特征")
    parser.add_argument("--dry-run", action="store_true", help="仅检查不写入")
    args = parser.parse_args()

    market = args.market
    parquet_name = MARKET_PARQUET_NAMES[market]
    parquet_path = FEATURE_SNAPSHOT_DIR / parquet_name

    _log(f"市场: {market}")
    _log(f"输出: {parquet_path}")

    # 加载 H5 数据
    df = load_h5_data(market)

    if df.empty:
        _log("ERROR: H5 数据为空")
        sys.exit(1)

    # 增量模式：检查现有 parquet
    existing = None
    if parquet_path.exists() and not args.rebuild:
        _log(f"读取现有 parquet: {parquet_path}")
        existing = pd.read_parquet(str(parquet_path), engine="pyarrow")
        existing["trade_date"] = pd.to_datetime(existing["trade_date"]).dt.date
        max_date = existing["trade_date"].max()
        _log(f"  现有数据: {len(existing):,} 行, 最新日期: {max_date}")

        # 只计算新数据
        new_dates = sorted(df["trade_date"].unique())
        new_dates = [d for d in new_dates if d > max_date]
        if not new_dates:
            _log("无需更新（parquet 已是最新）")
            return
        _log(f"  需要计算: {len(new_dates)} 天新数据")
        df = df[df["trade_date"].isin(new_dates)]

    if args.dry_run:
        _log(f"DRY RUN: 将计算 {len(df):,} 行, {df['instrument'].nunique()} 个标的")
        return

    # 计算特征
    new_data = compute_market_features(df, market)
    _log(f"  计算完成: {len(new_data):,} 行, {len(new_data.columns)} 列")

    if new_data.empty:
        _log("没有有效数据")
        return

    # 合并
    if existing is not None and not args.rebuild:
        # 对齐列
        all_cols = list(dict.fromkeys(list(existing.columns) + [c for c in new_data.columns if c not in existing.columns]))
        for c in all_cols:
            if c not in existing.columns:
                existing[c] = 0
            if c not in new_data.columns:
                new_data[c] = 0
        existing = existing[all_cols]
        new_data = new_data[all_cols]
        combined = pd.concat([existing, new_data], ignore_index=True)
    else:
        combined = new_data

    combined = combined.sort_values(["trade_date", "instrument"]).reset_index(drop=True)

    _log(f"合并后: {len(combined):,} 行, {len(combined.columns)} 列")
    _log(f"日期: {combined['trade_date'].min()} ~ {combined['trade_date'].max()}")

    # 写入
    combined.to_parquet(str(parquet_path), index=False, engine="pyarrow")
    _log(f"已写入: {parquet_path} ({parquet_path.stat().st_size / 1024 / 1024:.1f}MB)")

    # 验证
    verify = pd.read_parquet(str(parquet_path), engine="pyarrow")
    _log(f"验证: {len(verify):,} 行, {len(verify.columns)} 列")

    # 特征覆盖检查
    latest = verify[verify["trade_date"] == verify["trade_date"].max()]
    _log(f"最新日期 {len(latest)} 个标的:")
    for col_group, cols in [
        ("OHLCV", ["open", "high", "low", "close", "volume"]),
        ("动量", ["mom_ret_1d", "mom_ret_5d", "mom_rsi_14"]),
        ("波动率", ["vol_std_20", "vol_atr_14"]),
        ("流动性", ["liq_volume", "liq_amihud_20"]),
        ("资金流", ["flow_net_amount", "flow_vpin"]),
    ]:
        coverage = []
        for col in cols:
            if col in latest.columns:
                non_null = latest[col].notna().sum()
                coverage.append(f"{col}={non_null}")
        _log(f"  [{col_group}] {', '.join(coverage)}")

    _log("完成!")


if __name__ == "__main__":
    main()
