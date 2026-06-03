#!/usr/bin/env python3
"""更新 model_features_2026.parquet，从 stock_daily_latest 补充缺失日期。

从 DB 读取 OHLCV + 基本面 + 指数成分 + 概念标签数据，
计算全部模型特征（原有 51 + 新增 ~36 = ~87 个），更新 parquet。

用法:
    python update_feature_parquet.py                    # 自动补充所有缺失日期
    python update_feature_parquet.py --since 2026-05-23  # 从指定日期开始
    python update_feature_parquet.py --rebuild           # 重建全部日期
    python update_feature_parquet.py --dry-run           # 仅检查，不写入
"""

import argparse
import asyncio
import os
import sys
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

# 容器内 vs 主机
if os.path.exists("/app") and not os.environ.get("QUANTMIND_HOST_MODE"):
    PARQUET_PATH = Path("/app/db/feature_snapshots/model_features_2026.parquet")
    DB_URL = "postgresql://quantmind:quantmind2026@db:5432/quantmind"
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    PARQUET_PATH = PROJECT_ROOT / "db" / "feature_snapshots" / "model_features_2026.parquet"
    DB_URL = "postgresql://quantmind:quantmind2026@localhost:5432/quantmind"


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ═══════════════════════════════════════════════════════════════════════════
# 数据读取
# ═══════════════════════════════════════════════════════════════════════════

# 从 DB 读取的列
DB_OHLCV_COLS = [
    "symbol", "trade_date", "open", "high", "low", "close", "volume", "amount", "adj_factor",
]
DB_FUNDAMENTAL_COLS = [
    "pe_ttm", "pb", "roe", "bp", "ep_ttm", "ln_mv_total", "float_mv", "total_mv",
    "industry", "is_st", "listing_market",
]
DB_INDEX_COLS = [
    "idx_all", "idx_hs300", "idx_zz1000", "idx_chinext", "idx_margin",
]
DB_CONCEPT_COLS = [
    "concept_ai", "concept_chip", "concept_new_energy", "concept_pv",
    "concept_military", "concept_medical", "concept_fintech",
    "concept_consumption", "concept_state_owned", "concept_lithium",
]
DB_TECHNICAL_COLS = [
    "return_1d", "return_5d", "return_20d", "ma5", "ma20", "ma60",
    "rsi_14", "kdj_k", "macd_hist", "vol_std_20", "vol_atr_14",
    "turnover_rate", "beta_20",
    "flow_net_amount", "volume_ma_5", "amount_ma_5",
]

ALL_DB_COLS = list(dict.fromkeys(
    DB_OHLCV_COLS + DB_FUNDAMENTAL_COLS + DB_INDEX_COLS + DB_CONCEPT_COLS + DB_TECHNICAL_COLS
))


async def fetch_data(since: date, until: date, lookback_days: int = 120) -> pd.DataFrame:
    """从 stock_daily_latest 读取数据（含 lookback 窗口）。"""
    import asyncpg

    conn = await asyncpg.connect(DB_URL)
    try:
        # 只查询存在的列
        cols_str = ", ".join(ALL_DB_COLS)
        rows = await conn.fetch(f"""
            SELECT {cols_str}
            FROM stock_daily_latest
            WHERE trade_date BETWEEN $1 AND $2
            ORDER BY symbol, trade_date
        """, since - timedelta(days=lookback_days), until)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame([dict(r) for r in rows])
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df
    finally:
        await conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# 特征计算
# ═══════════════════════════════════════════════════════════════════════════

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


def compute_features_for_group(g: pd.DataFrame) -> pd.DataFrame:
    """为单只股票计算全部特征。输入需按 trade_date 排序。"""
    g = g.sort_values("trade_date").copy()
    c = g["close"]
    h = g["high"]
    lo = g["low"]
    v = g["volume"]
    amt = g["amount"]
    ret = c.pct_change()
    ln_c = np.log(c.clip(lower=1e-8))
    log_ret = ln_c.diff()

    # ═══ 原有 51 个特征 ═══

    # ── 动量 ──
    g["mom_ret_1d"] = ret
    g["mom_ret_5d"] = c.pct_change(5)
    g["mom_ret_10d"] = c.pct_change(10)
    g["mom_ret_20d"] = c.pct_change(20)
    g["mom_ma_gap_5"] = (c / c.rolling(5, min_periods=1).mean()) - 1
    g["mom_ma_gap_20"] = (c / c.rolling(20, min_periods=1).mean()) - 1
    g["mom_macd_hist"] = _macd(c)[2]
    g["mom_rsi_14"] = _rsi(c, 14)
    g["mom_kdj_k"] = _kdj(h, lo, c)[0]
    g["mom_breakout_20d"] = (c / c.rolling(20, min_periods=1).max()) - 1

    # ── 波动率 ──
    g["vol_std_20"] = log_ret.rolling(20, min_periods=5).std()
    tr = pd.concat([h - lo, (h - c.shift()).abs(), (lo - c.shift()).abs()], axis=1).max(axis=1)
    g["vol_atr_14"] = tr.rolling(14, min_periods=1).mean()
    hl_ratio = np.log(h / lo.clip(lower=1e-8))
    g["vol_parkinson_20"] = np.sqrt((hl_ratio ** 2).rolling(20, min_periods=5).mean() / (4 * np.log(2)))
    g["vol_gk_20"] = np.sqrt(
        (0.5 * (ln_c.diff() ** 2) - (2 * np.log(2) - 1) * (log_ret ** 2))
        .rolling(20, min_periods=5).mean().clip(lower=0)
    )
    g["vol_rs_20"] = np.sqrt((log_ret.clip(lower=0) ** 2).rolling(20, min_periods=5).mean())
    neg_ret = log_ret.clip(upper=0)
    g["vol_downside_20"] = neg_ret.rolling(20, min_periods=5).std()
    g["vol_realized_rv"] = np.sqrt((log_ret ** 2).rolling(20, min_periods=5).mean() * 252)
    rv = log_ret.rolling(20, min_periods=5).std()
    bv = (log_ret.abs() * log_ret.shift().abs()).rolling(20, min_periods=5).mean()
    bv = bv.clip(lower=1e-12)
    g["vol_jump_zadj"] = ((rv ** 2) / bv).clip(upper=10).fillna(0)

    # ── 流动性 ──
    g["liq_volume"] = v
    g["liq_amount"] = amt
    g["liq_turnover_os"] = v / v.rolling(250, min_periods=20).mean().clip(lower=1)
    g["liq_volume_ma_20"] = v.rolling(20, min_periods=1).mean()
    g["liq_volume_ratio_5"] = v / v.rolling(5, min_periods=1).mean().clip(lower=1) - 1
    g["liq_amount_ma_20"] = amt.rolling(20, min_periods=1).mean()
    g["liq_amount_ratio_5"] = amt / amt.rolling(5, min_periods=1).mean().clip(lower=1) - 1
    tp = (h + lo + c) / 3
    mf = tp * v
    pos_mf = mf * (tp > tp.shift()).astype(float)
    neg_mf = mf * (tp <= tp.shift()).astype(float)
    mfr = pos_mf.rolling(14, min_periods=1).sum() / neg_mf.rolling(14, min_periods=1).sum().replace(0, np.nan)
    g["liq_mfi_14"] = 100 - (100 / (1 + mfr))
    abs_ret = ret.abs()
    g["liq_amihud_20"] = (abs_ret / amt.clip(lower=1)).rolling(20, min_periods=1).mean()
    g["liq_amihud_60"] = (abs_ret / amt.clip(lower=1)).rolling(60, min_periods=5).mean()
    clv = ((c - lo) - (h - c)) / (h - lo).replace(0, np.nan)
    clv = clv.fillna(0)
    g["liq_accdist_20"] = (clv * v).rolling(20, min_periods=1).sum()

    # ── 资金流 ──
    direction = np.sign(c.diff())
    g["flow_net_amount"] = (amt * direction).rolling(5, min_periods=1).sum()
    g["flow_net_amount_ratio"] = g["flow_net_amount"] / amt.rolling(20, min_periods=1).sum().clip(lower=1)
    g["flow_large_net_amount"] = 0.0
    buy_vol = v * (c > c.shift()).astype(float)
    sell_vol = v * (c <= c.shift()).astype(float)
    g["flow_vpin"] = (buy_vol - sell_vol).abs().rolling(20, min_periods=5).sum() / v.rolling(20, min_periods=5).sum().clip(lower=1)
    g["flow_vpin_ma_5"] = g["flow_vpin"].rolling(5, min_periods=1).mean()
    g["flow_vpin_ma_20"] = g["flow_vpin"].rolling(20, min_periods=1).mean()

    # ── 风格因子 ──
    g["style_ln_mv_total"] = np.log(amt.clip(lower=1))
    g["style_ln_mv_float"] = g["style_ln_mv_total"] * 0.9
    # beta = cov(ret, market) / var(market); proxy: rolling mean / rolling std
    ret_ma20 = ret.rolling(20, min_periods=5).mean()
    ret_std20 = ret.rolling(20, min_periods=5).std().clip(lower=1e-12)
    g["style_beta_20"] = ret_ma20 / ret_std20
    ret_ma60 = ret.rolling(60, min_periods=10).mean()
    ret_std60 = ret.rolling(60, min_periods=10).std().clip(lower=1e-12)
    g["style_beta_60"] = ret_ma60 / ret_std60
    g["style_idio_vol_20"] = log_ret.rolling(20, min_periods=5).std()
    g["style_residual_ret_20"] = ret.rolling(20, min_periods=5).mean()

    # ── 行业 ──
    g["ind_ret_1d"] = 0.0
    g["ind_ret_20d"] = 0.0
    g["ind_strength_20"] = 0.0
    g["ind_momentum_rank_20"] = 0.5

    # ═══ 新增动量特征（纯 OHLCV 计算，不依赖后续变量） ═══
    g["mom_ret_3d"] = c.pct_change(3)
    g["mom_ret_60d"] = c.pct_change(60)
    g["mom_ret_120d"] = c.pct_change(120)
    g["mom_ma_gap_10"] = (c / c.rolling(10, min_periods=1).mean()) - 1
    g["mom_ma_gap_60"] = (c / c.rolling(60, min_periods=1).mean()) - 1
    g["mom_ma_gap_120"] = (c / c.rolling(120, min_periods=1).mean()) - 1
    ema12 = _ema(c, 12)
    ema26 = _ema(c, 26)
    g["mom_ema_gap_12"] = (c / ema12) - 1
    g["mom_ema_gap_26"] = (c / ema26) - 1
    g["mom_roc_12"] = c.pct_change(12)

    # ═══ 新增波动率特征 ═══
    g["vol_std_10"] = log_ret.rolling(10, min_periods=3).std()
    g["vol_atr_20"] = tr.rolling(20, min_periods=1).mean()
    g["vol_true_range"] = tr  # raw true range
    g["vol_parkinson_10"] = np.sqrt((hl_ratio ** 2).rolling(10, min_periods=3).mean() / (4 * np.log(2)))
    g["vol_gk_10"] = np.sqrt(
        (0.5 * (ln_c.diff() ** 2) - (2 * np.log(2) - 1) * (log_ret ** 2))
        .rolling(10, min_periods=3).mean().clip(lower=0)
    )
    g["vol_rs_10"] = np.sqrt((log_ret.clip(lower=0) ** 2).rolling(10, min_periods=3).mean())
    pos_ret = log_ret.clip(lower=0)
    g["vol_upside_20"] = pos_ret.rolling(20, min_periods=5).std()
    # realized relative vol (rv / bv ratio)
    rv_20 = log_ret.rolling(20, min_periods=5).std()
    bv_20 = (log_ret.abs() * log_ret.shift().abs()).rolling(20, min_periods=5).mean().clip(lower=1e-12)
    g["vol_realized_rrv"] = (rv_20 / bv_20).clip(upper=10).fillna(0)
    # realized skewness & kurtosis (vectorized approximation)
    lr_mean = log_ret.rolling(20, min_periods=10).mean()
    lr_std = log_ret.rolling(20, min_periods=10).std().clip(lower=1e-12)
    lr_z = (log_ret - lr_mean) / lr_std
    g["vol_realized_rskew"] = (lr_z ** 3).rolling(20, min_periods=10).mean()
    g["vol_realized_rkurt"] = (lr_z ** 4).rolling(20, min_periods=10).mean() - 3
    # jump ratios
    rv_sq = rv_20 ** 2
    bv_val = bv_20
    g["vol_jump_rjv_ratio"] = (rv_sq / bv_val).clip(upper=10).fillna(0)
    bipower_var = (log_ret.abs() * log_ret.shift().abs()).rolling(20, min_periods=5).mean()
    jump_var = (rv_sq - bipower_var).clip(lower=0)
    g["vol_jump_sjv_ratio"] = (jump_var / rv_sq.replace(0, np.nan)).fillna(0).clip(upper=1)

    # ═══ 新增流动性特征 ═══
    g["liq_turnover_tl"] = g["turnover_rate"]  # alias
    g["liq_volume_ma_5"] = v.rolling(5, min_periods=1).mean()
    g["liq_volume_ma_10"] = v.rolling(10, min_periods=1).mean()
    g["liq_volume_ratio_20"] = v / v.rolling(20, min_periods=1).mean().clip(lower=1) - 1
    g["liq_amount_ma_5"] = amt.rolling(5, min_periods=1).mean()
    g["liq_amount_ma_10"] = amt.rolling(10, min_periods=1).mean()
    g["liq_amount_ratio_20"] = amt / amt.rolling(20, min_periods=1).mean().clip(lower=1) - 1
    # OBV (On-Balance Volume)
    obv_direction = np.sign(c.diff())
    obv_raw = (v * obv_direction).cumsum()
    g["liq_obv_20"] = obv_raw - obv_raw.rolling(20, min_periods=1).mean()
    g["liq_obv_60"] = obv_raw - obv_raw.rolling(60, min_periods=1).mean()

    # ═══ 新增资金流特征 ═══
    g["flow_vpin_delta_5"] = g["flow_vpin"].diff(5)
    # approximate order count from volume pattern
    g["flow_net_order_count"] = (v * direction).rolling(5, min_periods=1).sum()
    g["flow_net_order_ratio"] = g["flow_net_order_count"] / v.rolling(20, min_periods=1).sum().clip(lower=1)
    # pressure index: cumulative money flow direction
    g["flow_pressure_index"] = (amt * direction).rolling(20, min_periods=1).sum() / amt.rolling(20, min_periods=1).sum().clip(lower=1)

    # ═══ 新增风格因子 ═══
    ret_ma120 = ret.rolling(120, min_periods=20).mean()
    ret_std120 = ret.rolling(120, min_periods=20).std().clip(lower=1e-12)
    g["style_beta_120"] = ret_ma120 / ret_std120
    g["style_idio_vol_60"] = log_ret.rolling(60, min_periods=10).std()
    g["style_bp"] = g["bp"]  # alias
    g["style_ep_ttm"] = g["ep_ttm"]  # alias

    # ── 辅助列 ──
    g["factor"] = g["adj_factor"]
    g["pctchange"] = ret

    # ═══ 新增特征：从 DB 直接使用（已有值保留，NULL 填 0） ═══

    # 基本面
    for col in DB_FUNDAMENTAL_COLS:
        if col in g.columns:
            if col in ("industry", "is_st", "listing_market"):
                # 分类列保持原样
                pass
            else:
                g[col] = pd.to_numeric(g[col], errors="coerce").fillna(0)
        else:
            g[col] = 0

    # 指数成分 / 概念标签（0/1 标记）
    for col in DB_INDEX_COLS + DB_CONCEPT_COLS:
        if col in g.columns:
            g[col] = pd.to_numeric(g[col], errors="coerce").fillna(0).astype(int)
        else:
            g[col] = 0

    # 技术指标（DB 已计算的，优先用 DB 值，NULL 用 OHLCV 重算）
    if "return_1d" in g.columns:
        g["return_1d"] = pd.to_numeric(g["return_1d"], errors="coerce").fillna(ret)
    else:
        g["return_1d"] = ret

    if "return_5d" in g.columns:
        g["return_5d"] = pd.to_numeric(g["return_5d"], errors="coerce").fillna(c.pct_change(5))
    else:
        g["return_5d"] = c.pct_change(5)

    if "return_20d" in g.columns:
        g["return_20d"] = pd.to_numeric(g["return_20d"], errors="coerce").fillna(c.pct_change(20))
    else:
        g["return_20d"] = c.pct_change(20)

    # 移动平均
    if "ma5" not in g.columns or g["ma5"].isna().all():
        g["ma5"] = c.rolling(5, min_periods=1).mean()
    else:
        g["ma5"] = pd.to_numeric(g["ma5"], errors="coerce").fillna(c.rolling(5, min_periods=1).mean())

    if "ma20" not in g.columns or g["ma20"].isna().all():
        g["ma20"] = c.rolling(20, min_periods=1).mean()
    else:
        g["ma20"] = pd.to_numeric(g["ma20"], errors="coerce").fillna(c.rolling(20, min_periods=1).mean())

    if "ma60" not in g.columns or g["ma60"].isna().all():
        g["ma60"] = c.rolling(60, min_periods=1).mean()
    else:
        g["ma60"] = pd.to_numeric(g["ma60"], errors="coerce").fillna(c.rolling(60, min_periods=1).mean())

    # 均线偏离
    g["ma_gap_5"] = (c / g["ma5"]) - 1
    g["ma_gap_20"] = (c / g["ma20"]) - 1

    # RSI
    if "rsi_14" not in g.columns or g["rsi_14"].isna().all():
        g["rsi_14"] = _rsi(c, 14)
    else:
        g["rsi_14"] = pd.to_numeric(g["rsi_14"], errors="coerce").fillna(_rsi(c, 14))

    g["rsi_6"] = _rsi(c, 6)

    # KDJ
    kdj_k, kdj_d, kdj_j = _kdj(h, lo, c)
    if "kdj_k" not in g.columns or g["kdj_k"].isna().all():
        g["kdj_k"] = kdj_k
    else:
        g["kdj_k"] = pd.to_numeric(g["kdj_k"], errors="coerce").fillna(kdj_k)
    g["kdj_d"] = kdj_d
    g["kdj_j"] = kdj_j

    # MACD
    macd_dif, macd_dea, macd_hist = _macd(c)
    if "macd_hist" not in g.columns or g["macd_hist"].isna().all():
        g["macd_hist"] = macd_hist
    else:
        g["macd_hist"] = pd.to_numeric(g["macd_hist"], errors="coerce").fillna(macd_hist)
    g["macd_dif"] = macd_dif
    g["macd_dea"] = macd_dea

    # 动量别名（catalog key 匹配）
    g["mom_macd_dif"] = macd_dif
    g["mom_macd_dea"] = macd_dea
    g["mom_rsi_6"] = g["rsi_6"]
    g["mom_kdj_d"] = kdj_d
    g["mom_kdj_j"] = kdj_j

    # 波动率补充
    g["vol_std_5"] = log_ret.rolling(5, min_periods=2).std()
    g["vol_std_60"] = log_ret.rolling(60, min_periods=10).std()
    if "vol_std_20" in g.columns:
        g["vol_std_20"] = pd.to_numeric(g["vol_std_20"], errors="coerce").fillna(log_ret.rolling(20, min_periods=5).std())
    if "vol_atr_14" in g.columns:
        g["vol_atr_14"] = pd.to_numeric(g["vol_atr_14"], errors="coerce").fillna(tr.rolling(14, min_periods=1).mean())

    # 成交量比率
    g["volume_ratio_5"] = v / v.rolling(5, min_periods=1).mean().clip(lower=1)
    g["volume_ratio_20"] = v / v.rolling(20, min_periods=1).mean().clip(lower=1)
    g["volume_ma_5"] = v.rolling(5, min_periods=1).mean()
    g["volume_ma_3"] = v.rolling(3, min_periods=1).mean()
    g["amount_ma_5"] = amt.rolling(5, min_periods=1).mean()

    # 换手率
    if "turnover_rate" in g.columns:
        g["turnover_rate"] = pd.to_numeric(g["turnover_rate"], errors="coerce").fillna(
            v / v.rolling(250, min_periods=20).mean().clip(lower=1)
        )
    else:
        g["turnover_rate"] = v / v.rolling(250, min_periods=20).mean().clip(lower=1)

    # Beta
    if "beta_20" in g.columns:
        g["beta_20"] = pd.to_numeric(g["beta_20"], errors="coerce").fillna(
            ret_ma20 / ret_std20
        )

    # 市值相关
    if "ln_mv_total" in g.columns:
        g["ln_mv_total"] = pd.to_numeric(g["ln_mv_total"], errors="coerce").fillna(np.log(amt.clip(lower=1)))

    # bp / ep_ttm
    if "bp" in g.columns:
        g["bp"] = pd.to_numeric(g["bp"], errors="coerce").fillna(0)
    if "ep_ttm" in g.columns:
        g["ep_ttm"] = pd.to_numeric(g["ep_ttm"], errors="coerce").fillna(0)

    # is_st
    if "is_st" in g.columns:
        g["is_st"] = pd.to_numeric(g["is_st"], errors="coerce").fillna(0).astype(int)

    # ═══ Alpha158 K 线形态因子 (9 个) ═══
    # 来源: Qlib Alpha158 — 仅需 OHLCV，无窗口依赖
    o = g["open"]
    denom = (h - lo).replace(0, np.nan)
    g["kline_kmid"] = (c - o) / o.clip(lower=1e-8)                              # 实体比
    g["kline_klen"] = (h - lo) / o.clip(lower=1e-8)                             # 振幅比
    g["kline_kmid2"] = (c - o) / denom                                          # 实体占振幅比
    g["kline_kup"] = (h - pd.concat([o, c], axis=1).max(axis=1)) / o.clip(lower=1e-8)   # 上影线比
    g["kline_kup2"] = (h - pd.concat([o, c], axis=1).max(axis=1)) / denom              # 上影线占振幅比
    g["kline_klow"] = (pd.concat([o, c], axis=1).min(axis=1) - lo) / o.clip(lower=1e-8) # 下影线比
    g["kline_klow2"] = (pd.concat([o, c], axis=1).min(axis=1) - lo) / denom             # 下影线占振幅比
    g["kline_ksft"] = (2 * c - h - lo) / o.clip(lower=1e-8)                     # 重心偏移
    g["kline_ksft2"] = (2 * c - h - lo) / denom                                  # 重心偏移归一化

    # ═══ Alpha158 价格相对因子 (4 个) ═══
    g["prel_open0"] = o / c.clip(lower=1e-8)                                    # 开盘/收盘
    g["prel_high0"] = h / c.clip(lower=1e-8)                                    # 最高/收盘
    g["prel_low0"] = lo / c.clip(lower=1e-8)                                    # 最低/收盘
    vwap = amt / v.clip(lower=1)                                                 # VWAP = 成交额/成交量
    vwap = vwap.replace([np.inf, -np.inf], np.nan).fillna((h + lo + c) / 3)     # fallback: 典型价格
    g["prel_vwap0"] = vwap / c.clip(lower=1e-8)                                 # VWAP/收盘

    # ═══ 第一梯队: 价格位置因子 (5 个) ═══
    # 价格在N日区间的位置 (0=最低, 1=最高)
    low_20 = lo.rolling(20, min_periods=1).min()
    high_20 = h.rolling(20, min_periods=1).max()
    g["price_position_20"] = (c - low_20) / (high_20 - low_20).clip(lower=1e-8)

    low_60 = lo.rolling(60, min_periods=1).min()
    high_60 = h.rolling(60, min_periods=1).max()
    g["price_position_60"] = (c - low_60) / (high_60 - low_60).clip(lower=1e-8)

    # 距离N日新高的回撤幅度
    g["dist_to_high_20"] = c / high_20.clip(lower=1e-8) - 1
    g["dist_to_low_20"] = c / low_20.clip(lower=1e-8) - 1

    # 20日内收益率排名 (0~1) — 向量化近似
    ret_1d = c.pct_change()
    ret_min_20 = ret_1d.rolling(20, min_periods=5).min()
    ret_max_20 = ret_1d.rolling(20, min_periods=5).max()
    g["ret_rank_20"] = (ret_1d - ret_min_20) / (ret_max_20 - ret_min_20).clip(lower=1e-8)

    # ═══ 第二梯队: 波动率调整动量 (4 个) ═══
    # Sharpe型动量 = 收益 / 波动率
    ret_std_5 = ret_1d.rolling(5, min_periods=2).std()
    ret_std_20 = ret_1d.rolling(20, min_periods=5).std()
    ret_std_60 = ret_1d.rolling(60, min_periods=10).std()
    g["mom_sharpe_5"] = c.pct_change(5) / ret_std_5.clip(lower=1e-6)
    g["mom_sharpe_20"] = c.pct_change(20) / ret_std_20.clip(lower=1e-6)
    g["mom_sharpe_60"] = c.pct_change(60) / ret_std_60.clip(lower=1e-6)

    # 风险调整后的相对强度
    ret_20 = c.pct_change(20)
    g["mom_risk_adj_20"] = (ret_20 - ret_20.rolling(20, min_periods=5).mean()) / ret_std_20.clip(lower=1e-6)

    # ═══ 第三梯队: 量价配合度 (4 个) ═══
    log_vol = np.log(v.clip(lower=1))

    # 量价相关性 (正=量价齐升)
    g["pv_corr_20"] = ret_1d.rolling(20, min_periods=10).corr(log_vol)
    g["pv_corr_10"] = ret_1d.rolling(10, min_periods=5).corr(log_vol)

    # 放量上涨占比 (20日里上涨日成交量占总量比)
    up_vol = pd.Series(np.where(ret_1d > 0, v, 0), index=g.index)
    g["up_volume_ratio_20"] = up_vol.rolling(20, min_periods=5).sum() / v.rolling(20, min_periods=5).sum().clip(lower=1e-6)

    # 量价背离 (价格排名 - 成交量排名) — 向量化近似
    c_min_20 = c.rolling(20, min_periods=5).min()
    c_max_20 = c.rolling(20, min_periods=5).max()
    v_min_20 = v.rolling(20, min_periods=5).min()
    v_max_20 = v.rolling(20, min_periods=5).max()
    c_rank = (c - c_min_20) / (c_max_20 - c_min_20).clip(lower=1e-8)
    v_rank = (v - v_min_20) / (v_max_20 - v_min_20).clip(lower=1e-8)
    g["pv_divergence_20"] = c_rank - v_rank

    # ═══ 第四梯队: 趋势质量因子 (3 个) ═══
    # 20日趋势R² — 向量化: R² = corr(price, time_index)²
    time_idx = pd.Series(np.arange(len(c), dtype=float), index=c.index)
    g["trend_r2_20"] = c.rolling(20, min_periods=10).corr(time_idx) ** 2

    # 20日趋势斜率 — 向量化: slope = corr * std(price) / std(t) / mean(price)
    c_std_20 = c.rolling(20, min_periods=10).std()
    t_std = np.sqrt((np.arange(20) - np.arange(20).mean()) ** 2).sum() / 20
    corr_ct = c.rolling(20, min_periods=10).corr(time_idx)
    g["trend_slope_20"] = corr_ct * c_std_20 / (t_std + 1e-6) / c.rolling(20, min_periods=10).mean().clip(lower=1e-6)

    # 连续上涨/下跌强度 (5日涨跌天数差)
    up_down = pd.Series(np.where(ret_1d > 0, 1, np.where(ret_1d < 0, -1, 0)), index=g.index)
    g["consecutive_updown_5"] = up_down.rolling(5, min_periods=1).sum()

    # ═══ 第五梯队: 时序滞后特征 (2 个) ═══
    g["ret_1d_lag1"] = ret_1d.shift(1)
    g["ret_1d_lag2"] = ret_1d.shift(2)

    return g


def compute_all_features(df: pd.DataFrame, target_dates: set) -> pd.DataFrame:
    """为所有股票计算特征，只返回 target_dates 中的数据。"""
    _log(f"  计算特征（{df['symbol'].nunique()} 只股票）...")
    results = []
    total = df["symbol"].nunique()
    done = 0

    for sym, group in df.groupby("symbol"):
        feat = compute_features_for_group(group)
        results.append(feat)
        done += 1
        if done % 1000 == 0:
            _log(f"    进度: {done}/{total}")

    all_feat = pd.concat(results, ignore_index=True)
    all_feat = all_feat[all_feat["trade_date"].isin(target_dates)].copy()
    return all_feat


# ═══════════════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="更新 feature parquet")
    parser.add_argument("--since", default="", help="起始日期 (默认: parquet 最后日期+1)")
    parser.add_argument("--until", default="", help="截止日期 (默认: 今天)")
    parser.add_argument("--dry-run", action="store_true", help="仅检查不写入")
    parser.add_argument("--rebuild", action="store_true", help="重建全部特征")
    args = parser.parse_args()

    if not PARQUET_PATH.exists():
        _log(f"ERROR: parquet 文件不存在: {PARQUET_PATH}")
        sys.exit(1)

    # 读取现有 parquet
    _log(f"读取现有 parquet: {PARQUET_PATH}")
    existing = pd.read_parquet(PARQUET_PATH, engine="pyarrow")
    existing["trade_date"] = pd.to_datetime(existing["trade_date"]).dt.date
    max_date = existing["trade_date"].max()
    _log(f"  现有数据: {len(existing):,} 行, {existing['symbol'].nunique()} 只股票")
    _log(f"  日期范围: {existing['trade_date'].min()} ~ {max_date}")

    # 确定日期范围
    since = date.fromisoformat(args.since) if args.since else max_date + timedelta(days=1)
    until = date.fromisoformat(args.until) if args.until else date.today()

    if args.rebuild:
        since = existing["trade_date"].min()
        _log(f"  REBUILD 模式: 重建 {since} ~ {until}")

    _log(f"  需要补充: {since} ~ {until}")

    if since > until and not args.rebuild:
        _log("无需更新（parquet 已是最新）")
        return

    if args.dry_run:
        _log("DRY RUN 模式，不写入")
        return

    # 从 DB 读取数据
    _log("从 stock_daily_latest 读取数据（含 120 天 lookback）...")
    db_df = asyncio.run(fetch_data(since, until, lookback_days=120))

    if db_df.empty:
        _log("DB 中没有新数据")
        return

    _log(f"  读取到 {len(db_df):,} 行, {db_df['symbol'].nunique()} 只股票")

    # 计算特征
    target_dates = set()
    d = since
    while d <= until:
        target_dates.add(d)
        d += timedelta(days=1)

    new_data = compute_all_features(db_df, target_dates)
    _log(f"  计算完成: {len(new_data):,} 行")

    if new_data.empty:
        _log("没有有效数据")
        return

    # 确定输出列（parquet 已有列 + 新增列，去重）
    existing_cols = set(existing.columns)
    new_cols = set(new_data.columns)
    all_cols = list(dict.fromkeys(list(existing.columns) + [c for c in new_data.columns if c not in existing_cols]))
    new_data = new_data.reindex(columns=all_cols, fill_value=0)

    # 合并
    if args.rebuild:
        combined = new_data
    else:
        overlap_dates = set(new_data["trade_date"].unique()) & set(existing["trade_date"].unique())
        if overlap_dates:
            _log(f"  发现重叠日期 {len(overlap_dates)} 天，将覆盖")
            existing = existing[~existing["trade_date"].isin(overlap_dates)]
        # 对齐列
        for c in all_cols:
            if c not in existing.columns:
                existing[c] = 0
        existing = existing[all_cols]
        combined = pd.concat([existing, new_data], ignore_index=True)

    combined = combined.sort_values(["trade_date", "symbol"]).reset_index(drop=True)

    _log(f"合并后: {len(combined):,} 行, {len(combined.columns)} 列")
    _log(f"日期: {combined['trade_date'].min()} ~ {combined['trade_date'].max()}")

    # 写入 parquet
    combined.to_parquet(str(PARQUET_PATH), index=False, engine="pyarrow")
    _log(f"已写入: {PARQUET_PATH} ({PARQUET_PATH.stat().st_size / 1024 / 1024:.1f}MB)")

    # 验证
    verify = pd.read_parquet(PARQUET_PATH, engine="pyarrow")
    verify["trade_date"] = pd.to_datetime(verify["trade_date"]).dt.date
    _log(f"验证: {len(verify):,} 行, {len(verify.columns)} 列, 最新日期 {verify['trade_date'].max()}")

    # 检查覆盖率
    latest = verify[verify["trade_date"] == verify["trade_date"].max()]
    _log(f"最新日期 {len(latest)} 只股票:")
    for col_group, cols in [
        ("OHLCV", ["open", "high", "low", "close", "volume"]),
        ("动量", ["mom_ret_1d", "mom_ret_5d", "mom_rsi_14"]),
        ("波动率", ["vol_std_20", "vol_atr_14"]),
        ("流动性", ["liq_volume", "liq_amihud_20"]),
        ("资金流", ["flow_net_amount", "flow_vpin"]),
        ("基本面", ["pe_ttm", "pb", "ln_mv_total"]),
        ("指数", ["idx_hs300", "idx_zz1000", "idx_chinext"]),
        ("概念", ["concept_ai", "concept_chip", "concept_new_energy"]),
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
