#!/usr/bin/env python3
"""
QuantMind 多周期集成推理脚本 (inference_ensemble.py)
=====================================================
同时运行多个预测周期（T+1, T+5, T+10, T+20）的模型，
通过加权融合 + 共识度生成最终信号。

优势：
- 多周期共识 = 更高确定性
- 短期+长期信号互补，减少噪音
- 自适应权重（可根据历史 IC 调整）

平台注入环境变量：
    MODEL_DIR      模型目录（含 ensemble_config.json）
    TRADE_DATE     推理日期
    OUTPUT_FORMAT  固定值 json

输出格式：
    [{"symbol": "SH600519", "score": 0.15, "consensus": 3, "detail": {...}}, ...]

exit code：0=成功, 1=致命错误, 2=数据不足
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("inference_ensemble")

_DEFAULT_DATA_DIR = "/app/db/feature_snapshots"


# ═══════════════════════════════════════════════════════════════════════════
# 1. 配置
# ═══════════════════════════════════════════════════════════════════════════

def load_ensemble_config(model_dir: Path) -> dict:
    """加载集成配置。如果不存在，自动扫描子目录发现模型。"""
    config_path = model_dir / "ensemble_config.json"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)

    # 自动发现：扫描 MODEL_DIR 的父目录下所有模型
    # 每个 horizon 选特征数最多的模型
    models_base = Path(os.getenv("MODELS_USERS_DIR", "/app/models/users/default/10000001"))
    best_per_horizon = {}

    for meta_path in sorted(models_base.glob("*/metadata.json")):
        m = json.load(open(meta_path, encoding="utf-8"))
        ctx = m.get("context", {})
        h = m.get("target_horizon_days", ctx.get("target_horizon_days"))
        ms = ctx.get("market", m.get("market", ""))
        if ms != "CN" or h is None:
            continue
        h = int(h)
        n = len(m.get("feature_columns", m.get("features", [])))
        d = meta_path.parent.name
        if h not in best_per_horizon or n > best_per_horizon[h]["features"]:
            best_per_horizon[h] = {"dir": d, "features": n}

    if not best_per_horizon:
        return {"models": []}

    # 默认权重：T+5 权重最高（中短期最稳定）
    default_weights = {1: 0.15, 3: 0.15, 5: 0.30, 10: 0.20, 20: 0.20}

    config = {
        "models": [
            {
                "horizon": h,
                "model_dir": str(models_base / info["dir"]),
                "weight": default_weights.get(h, 0.15),
                "features": info["features"],
            }
            for h, info in sorted(best_per_horizon.items())
        ]
    }
    logger.info("自动发现 %d 个周期模型: %s", len(config["models"]),
                ["T+" + str(m["horizon"]) for m in config["models"]])
    return config


# ═══════════════════════════════════════════════════════════════════════════
# 2. 单模型推理
# ═══════════════════════════════════════════════════════════════════════════

def load_model_and_meta(model_dir: Path) -> tuple[lgb.Booster, dict]:
    """加载单个模型及其元数据。"""
    meta_path = model_dir / "metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"metadata.json 不存在: {meta_path}")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    model_file = meta.get("model_file", "model.lgb")
    model_path = model_dir / model_file
    if not model_path.exists():
        candidates = list(model_dir.glob("*.lgb")) + list(model_dir.glob("*.txt"))
        if not candidates:
            raise FileNotFoundError(f"未找到模型文件: {model_dir}")
        model_path = candidates[0]

    model = lgb.Booster(model_file=str(model_path))
    return model, meta


def predict_single(
    model: lgb.Booster,
    meta: dict,
    day_df: pd.DataFrame,
) -> dict[str, float]:
    """对单个模型执行推理，返回 {symbol: score}。"""
    feature_cols = meta.get("feature_columns") or meta.get("features", [])
    fill_values = meta.get("fill_values", {})
    best_iter = meta.get("best_iteration")

    # 补缺失列
    missing = [c for c in feature_cols if c not in day_df.columns]
    if missing:
        for c in missing:
            day_df[c] = 0.0

    X = day_df[feature_cols].copy()
    for col, val in fill_values.items():
        if col in X.columns:
            X[col] = X[col].fillna(val)
    X = X.fillna(0.0)

    scores = model.predict(X.values.astype(np.float32), num_iteration=best_iter)
    symbols = day_df["symbol"].tolist()

    return {
        sym: float(s)
        for sym, s in zip(symbols, scores)
        if not (isinstance(s, float) and (s != s))
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3. 数据加载
# ═══════════════════════════════════════════════════════════════════════════

def _resolve_parquet_path(data_dir: Path, trade_date: str, market: str = "CN") -> Path | None:
    """解析 parquet 文件路径。"""
    _MARKET_PARQUET = {"HK": "model_features_hk.parquet", "US": "model_features_us.parquet", "CRYPTO": "model_features_crypto.parquet"}
    if market in _MARKET_PARQUET:
        p = data_dir / _MARKET_PARQUET[market]
        if p.exists():
            return p

    year = int(trade_date[:4])
    p = data_dir / f"model_features_{year}.parquet"
    if p.exists():
        return p

    p = data_dir / "model_features.parquet"
    return p if p.exists() else None


def load_day_data(trade_date: str, data_dir: Path) -> pd.DataFrame | None:
    """加载指定日期的特征数据。"""
    parquet_path = _resolve_parquet_path(data_dir, trade_date)
    if parquet_path is None:
        logger.warning("找不到 parquet 文件 (data_dir=%s)", data_dir)
        return None

    df = pd.read_parquet(parquet_path, engine="pyarrow")
    if "symbol" not in df.columns and "instrument" in df.columns:
        df = df.rename(columns={"instrument": "symbol"})
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    day_df = df[df["trade_date"] == trade_date].copy()

    if len(day_df) == 0:
        logger.warning("日期 %s 无数据", trade_date)
        return None

    # 过滤不可交易
    if "close" in day_df.columns:
        day_df = day_df[pd.to_numeric(day_df["close"], errors="coerce") > 0]
    if "volume" in day_df.columns:
        day_df = day_df[pd.to_numeric(day_df["volume"], errors="coerce") > 0]

    if len(day_df) == 0:
        return None

    logger.info("加载 %d 条记录，日期=%s", len(day_df), trade_date)
    return day_df


# ═══════════════════════════════════════════════════════════════════════════
# 4. 融合逻辑
# ═══════════════════════════════════════════════════════════════════════════

def fuse_scores(
    all_scores: dict[int, dict[str, float]],
    weights: dict[int, float],
) -> list[dict]:
    """多周期分数融合。

    融合策略：
    1. 每个周期的分数做截面标准化（z-score）
    2. 加权平均得到融合分数
    3. 统计共识度（多少个周期方向一致）

    Returns:
        [{"symbol": "...", "score": 0.15, "consensus": 3, "detail": {...}}, ...]
    """
    # 收集所有 symbol
    all_symbols = set()
    for scores in all_scores.values():
        all_symbols.update(scores.keys())

    # 预计算每个周期的排名百分位（避免 z-score 分布不一致问题）
    rank_pcts = {}
    for horizon, scores in all_scores.items():
        sorted_syms = sorted(scores.keys(), key=lambda s: scores[s])
        n = len(sorted_syms)
        rank_pcts[horizon] = {sym: (i + 1) / n for i, sym in enumerate(sorted_syms)}

    results = []
    for sym in all_symbols:
        raw_scores = {}
        pct_scores = {}

        for horizon, scores in sorted(all_scores.items()):
            if sym not in scores:
                continue
            raw_scores[horizon] = scores[sym]
            pct_scores[horizon] = rank_pcts[horizon].get(sym, 0.5)

        if not pct_scores:
            continue

        # 加权融合（基于排名百分位，0~1，0.5=中位数）
        total_weight = sum(weights.get(h, 0.1) for h in pct_scores)
        fused_pct = sum(
            pct_scores[h] * weights.get(h, 0.1) for h in pct_scores
        ) / total_weight

        # 转换为对称分数：(pct - 0.5) * 2，范围 [-1, 1]
        fused = (fused_pct - 0.5) * 2

        # 共识度：看涨(>0.5)或看跌(<0.5)方向一致的周期数
        directions = {h: 1 if p > 0.5 else -1 for h, p in pct_scores.items()}
        majority_dir = 1 if sum(directions.values()) > 0 else -1
        consensus = sum(1 for d in directions.values() if d == majority_dir)

        results.append({
            "symbol": sym,
            "score": float(fused),
            "consensus": int(consensus),
            "horizons": len(pct_scores),
            "detail": {
                "T+" + str(h): {
                    "raw": round(raw_scores.get(h, 0), 6),
                    "pct": round(pct_scores.get(h, 0.5), 4),
                }
                for h in sorted(pct_scores)
            },
        })

    return results


# ═══════════════════════════════════════════════════════════════════════════
# 5. 主流程
# ═══════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(description="多周期集成推理")
    p.add_argument("--date", "-d", type=str, default=os.getenv("TRADE_DATE", ""))
    p.add_argument("--output", "-o", type=str, required=True)
    p.add_argument("--model-dir", type=str, default=os.getenv("MODEL_DIR", str(Path(__file__).parent)))
    p.add_argument("--data-dir", type=str, default=os.getenv("MODEL_TRAINING_DATA_DIR", _DEFAULT_DATA_DIR))
    return p.parse_args()


def main():
    args = parse_args()

    trade_date = (args.date or "").strip()
    if not trade_date:
        logger.error("未指定推理日期")
        sys.exit(1)

    model_dir = Path(args.model_dir)
    data_dir = Path(args.data_dir)
    out_path = Path(args.output)

    logger.info("=== 多周期集成推理 ===")
    logger.info("  date     : %s", trade_date)
    logger.info("  model_dir: %s", model_dir)
    logger.info("  data_dir : %s", data_dir)

    # 1. 加载配置
    config = load_ensemble_config(model_dir)
    model_configs = config.get("models", [])
    if not model_configs:
        logger.error("无可用模型配置")
        sys.exit(1)

    logger.info("集成 %d 个周期: %s", len(model_configs),
                ["T+" + str(m["horizon"]) for m in model_configs])

    # 2. 加载数据
    day_df = load_day_data(trade_date, data_dir)
    if day_df is None:
        msg = f"日期 {trade_date} 无数据"
        logger.warning(msg)
        print(msg, file=sys.stderr)
        sys.exit(2)

    # 3. 逐模型推理
    all_scores = {}
    weights = {}

    for mc in model_configs:
        horizon = mc["horizon"]
        m_dir = Path(mc["model_dir"])
        w = mc.get("weight", 0.1)

        try:
            model, meta = load_model_and_meta(m_dir)
            scores = predict_single(model, meta, day_df.copy())
            all_scores[horizon] = scores
            weights[horizon] = w
            logger.info("T+%d: %d 条信号, weight=%.2f", horizon, len(scores), w)
        except Exception as e:
            logger.warning("T+%d 推理失败: %s", horizon, e)

    if not all_scores:
        logger.error("所有模型推理均失败")
        sys.exit(1)

    # 4. 融合
    signals = fuse_scores(all_scores, weights)
    signals.sort(key=lambda x: x["score"], reverse=True)

    logger.info("融合完成: %d 条信号", len(signals))

    # 统计共识度分布
    consensus_dist = {}
    for s in signals:
        c = s["consensus"]
        consensus_dist[c] = consensus_dist.get(c, 0) + 1
    logger.info("共识度分布: %s", dict(sorted(consensus_dist.items())))

    # 5. 输出
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(signals, f, ensure_ascii=False)

    logger.info("已写入: %s (%d 条)", out_path, len(signals))


if __name__ == "__main__":
    main()
