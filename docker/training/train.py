#!/usr/bin/env python3
"""
QuantMind 云端训练脚本 (CVM 容器内运行)
=========================================
参数传递方式：YAML 配置文件（固化在镜像中，参数通过挂载的 config.yaml 传入）

用法：
  docker run -v /host/workspace:/workspace quantmind:latest --config /workspace/config.yaml

config.yaml 结构：
  run_id / job_name
  data.train_start / data.train_end / data.features
  model.type / model.num_boost_round / model.val_ratio / model.params
  output.result_path
  callback.url / callback.secret
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import requests
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("quantmind.train")


# ── 硬件环境检测 ──────────────────────────────────────────────────────────────
def detect_hardware() -> dict[str, Any]:
    """检测运行环境的硬件配置（CPU、内存、GPU）。"""
    import os
    info: dict[str, Any] = {"cpu_count": os.cpu_count() or 1, "gpu_available": False, "gpu_count": 0, "gpu_name": "", "mem_total_gb": 0.0}
    try:
        import psutil
        info["mem_total_gb"] = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except ImportError:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            info["gpu_available"] = True
            info["gpu_count"] = torch.cuda.device_count()
            info["gpu_name"] = torch.cuda.get_device_name(0) if info["gpu_count"] > 0 else ""
    except ImportError:
        pass
    logger.info("Hardware: cpu=%d, mem=%.1fGB, gpu=%s(%d), gpu_name=%s",
                info["cpu_count"], info["mem_total_gb"],
                info["gpu_available"], info["gpu_count"], info["gpu_name"])
    return info


# ── 模型默认参数 ──────────────────────────────────────────────────────────────
DEFAULT_LGB_PARAMS: dict[str, Any] = {
    "objective":         "regression",
    "metric":            "l2",
    "boosting":          "gbdt",
    "num_leaves":        31,
    "learning_rate":     0.05,
    "feature_fraction":  0.6,
    "bagging_fraction":  0.7,
    "bagging_freq":      5,
    "min_child_samples": 50,
    "lambda_l1":         0.1,
    "lambda_l2":         1.0,
    "max_depth":         6,
    "path_smooth":       0.5,
    "n_jobs":            -1,
    "verbosity":         -1,
}

DEFAULT_XGB_PARAMS: dict[str, Any] = {
    "objective":        "reg:squarederror",
    "eval_metric":      "rmse",
    "max_depth":        6,
    "learning_rate":    0.05,
    "subsample":        0.7,
    "colsample_bytree": 0.6,
    "reg_alpha":        0.1,
    "reg_lambda":       1.0,
    "min_child_weight": 50,
    "tree_method":      "hist",
    "nthread":          -1,
    "verbosity":        0,
}

DEFAULT_CATBOOST_PARAMS: dict[str, Any] = {
    "loss_function":    "RMSE",
    "depth":            6,
    "learning_rate":    0.05,
    "iterations":       1000,
    "l2_leaf_reg":      3.0,
    "random_strength":  1.0,
    "bagging_temperature": 0.8,
    "od_type":          "Iter",
    "od_wait":          50,
    "thread_count":     -1,
    "verbose":          100,
}

# 支持的模型类型集合
_TREE_MODEL_TYPES = {"lightgbm", "xgboost", "catboost", "linear"}
_DL_MODEL_TYPES = {"gru", "lstm", "alstm", "transformer", "tabnet", "tcn"}
_ALL_MODEL_TYPES = _TREE_MODEL_TYPES | _DL_MODEL_TYPES

TRAINING_BASE_FEATURES: list[str] = [
    "mom_ret_1d",
    "mom_ret_5d",
    "mom_ret_20d",
    "liq_volume",
    "liq_amount",
    "liq_turnover_os",
]
_ALLOWED_SHAP_SPLIT = {"valid", "test", "train"}
_DEFAULT_EXPLAIN_CFG: dict[str, Any] = {
    "enable_shap": True,
    "shap_split": "valid",
    "shap_sample_rows": 30000,
}
_DEFAULT_SHAP_SAMPLE_ROWS = 30000
_MIN_SHAP_SAMPLE_ROWS = 1000
_MAX_SHAP_SAMPLE_ROWS = 100000
_SHAP_SAMPLE_RANDOM_STATE = 42


def _load_local_parquet(
    local_dir: Path,
    year: int,
    required_columns: list[str],
    clip_start: pd.Timestamp | None = None,
    clip_end: pd.Timestamp | None = None,
) -> pd.DataFrame | None:
    file_path = local_dir / f"model_features_{year}.parquet"
    if not file_path.exists():
        return None
    try:
        logger.info(f"Local data hit: {file_path}")

        schema_cols = set(pq.ParquetFile(file_path).schema_arrow.names)
        selected_cols = [c for c in required_columns if c in schema_cols]
        if "trade_date" not in selected_cols or "symbol" not in selected_cols:
            logger.warning(
                "Skip parquet missing required base columns trade_date/symbol: %s",
                file_path,
            )
            return None
        df = pd.read_parquet(file_path, columns=selected_cols, engine="pyarrow")

        # 先按日期裁剪每年数据，避免把无关年份全量堆进内存
        if "trade_date" in df.columns and (clip_start is not None or clip_end is not None):
            df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
            mask = pd.Series(True, index=df.index)
            if clip_start is not None:
                mask &= df["trade_date"] >= clip_start
            if clip_end is not None:
                mask &= df["trade_date"] <= clip_end
            df = df.loc[mask].copy()

        # 数值列统一降为 float32，降低内存峰值
        for col in df.columns:
            if col in {"trade_date", "symbol"}:
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].astype(np.float32, copy=False)

        return df
    except Exception as exc:
        logger.warning(f"  ⚠ Failed to read local parquet {file_path}: {exc}")
        return None


# ── 评估指标 ─────────────────────────────────────────────────────────────────
def _ic(pred: np.ndarray, label: np.ndarray) -> float:
    mask = np.isfinite(pred) & np.isfinite(label)
    if mask.sum() < 10:
        return float("nan")
    return float(np.corrcoef(pred[mask], label[mask])[0, 1])


def _rank_ic_series(df: pd.DataFrame, pred_col: str, label_col: str) -> list[float]:
    daily = []
    for _, g in df.groupby("trade_date", sort=False):
        g = g[[pred_col, label_col]].dropna()
        if len(g) < 10:
            continue
        rp = g[pred_col].rank(method="average").to_numpy()
        rl = g[label_col].rank(method="average").to_numpy()
        v = _ic(rp, rl)
        if np.isfinite(v):
            daily.append(v)
    return daily


def _compute_metrics(df: pd.DataFrame, y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    ic     = _ic(y_pred, y_true)
    series = _rank_ic_series(df.assign(_pred=y_pred, _label=y_true), "_pred", "_label")
    rank_ic   = float(np.nanmean(series)) if series else float("nan")
    rank_icir = float(np.mean(series) / (np.std(series) + 1e-9)) if series else float("nan")
    rmse = float(np.sqrt(np.mean(np.square(y_pred - y_true)))) if len(y_true) else float("nan")
    labels = (y_true > 0).astype(int)
    pos = int(labels.sum())
    neg = int(len(labels) - pos)
    auc = float("nan")
    if pos > 0 and neg > 0:
        ranks = pd.Series(y_pred).rank(method="average").to_numpy()
        auc = float((ranks[labels == 1].sum() - pos * (pos + 1) / 2.0) / (pos * neg))
    return {"ic": ic, "rank_ic": rank_ic, "rank_icir": rank_icir, "rmse": rmse, "auc": auc}


def _normalize_explain_cfg(raw: Any) -> dict[str, Any]:
    explain = raw if isinstance(raw, dict) else {}
    enable_shap = bool(explain.get("enable_shap", _DEFAULT_EXPLAIN_CFG["enable_shap"]))

    shap_split = str(explain.get("shap_split", _DEFAULT_EXPLAIN_CFG["shap_split"])).strip().lower()
    if shap_split not in _ALLOWED_SHAP_SPLIT:
        logger.warning("Invalid explain.shap_split=%s, fallback to 'valid'", shap_split)
        shap_split = "valid"

    sample_rows_raw = explain.get("shap_sample_rows", _DEFAULT_EXPLAIN_CFG["shap_sample_rows"])
    try:
        sample_rows = int(sample_rows_raw)
    except Exception:
        logger.warning("Invalid explain.shap_sample_rows=%s, fallback to %d", sample_rows_raw, _DEFAULT_SHAP_SAMPLE_ROWS)
        sample_rows = _DEFAULT_SHAP_SAMPLE_ROWS
    sample_rows = max(_MIN_SHAP_SAMPLE_ROWS, min(_MAX_SHAP_SAMPLE_ROWS, sample_rows))

    return {
        "enable_shap": enable_shap,
        "shap_split": shap_split,
        "shap_sample_rows": sample_rows,
    }


def _resolve_shap_source_frame(
    split_frames: dict[str, pd.DataFrame],
    preferred_split: str,
) -> tuple[str, pd.DataFrame]:
    ordered = [preferred_split] + [s for s in ("valid", "test", "train") if s != preferred_split]
    for split in ordered:
        frame = split_frames.get(split)
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            return split, frame
    return "", pd.DataFrame()


def _compute_shap_summary(
    *,
    model: lgb.Booster,
    split_frames: dict[str, pd.DataFrame],
    features: list[str],
    fill_values: dict[str, float],
    explain_cfg: dict[str, Any],
    out_path: Path,
) -> dict[str, Any]:
    shap_info: dict[str, Any] = {
        "enabled": bool(explain_cfg.get("enable_shap", True)),
        "status": "disabled",
        "split": str(explain_cfg.get("shap_split", "valid")),
        "rows_requested": int(explain_cfg.get("shap_sample_rows", _DEFAULT_SHAP_SAMPLE_ROWS)),
        "rows_used": 0,
        "file": "",
        "error": "",
        "elapsed_seconds": 0.0,
    }
    if not shap_info["enabled"]:
        return shap_info

    if not features:
        shap_info["status"] = "skipped"
        shap_info["error"] = "no_feature_columns"
        return shap_info

    start_ts = time.time()
    try:
        preferred_split = str(explain_cfg.get("shap_split", "valid")).strip().lower()
        selected_split, split_df = _resolve_shap_source_frame(split_frames, preferred_split)
        if split_df.empty:
            shap_info["status"] = "skipped"
            shap_info["error"] = "no_rows_for_shap"
            return shap_info

        rows_requested = int(explain_cfg.get("shap_sample_rows", _DEFAULT_SHAP_SAMPLE_ROWS))
        sample_df = split_df
        if len(sample_df) > rows_requested:
            sample_df = sample_df.sample(rows_requested, random_state=_SHAP_SAMPLE_RANDOM_STATE)

        x_df = sample_df[features].copy()
        for c in features:
            fill_v = fill_values.get(c, 0.0)
            if fill_v is None or (isinstance(fill_v, float) and np.isnan(fill_v)):
                fill_v = 0.0
            x_df[c] = x_df[c].astype("float32").fillna(fill_v)
        x = x_df.to_numpy(dtype=np.float32)

        contrib = model.predict(
            x,
            num_iteration=model.best_iteration or None,
            pred_contrib=True,
        )
        if not isinstance(contrib, np.ndarray) or contrib.ndim != 2:
            raise RuntimeError(f"unexpected SHAP contribution shape: {getattr(contrib, 'shape', None)}")
        if contrib.shape[1] < len(features):
            raise RuntimeError(f"contrib columns mismatch: got {contrib.shape[1]}, expect >= {len(features)}")

        shap_values = contrib[:, :len(features)]
        summary_df = pd.DataFrame(
            {
                "feature": features,
                "mean_abs_shap": np.mean(np.abs(shap_values), axis=0),
                "mean_shap": np.mean(shap_values, axis=0),
                "positive_ratio": np.mean(shap_values > 0, axis=0),
            }
        ).sort_values("mean_abs_shap", ascending=False)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        summary_df.to_csv(out_path, index=False)

        shap_info.update(
            {
                "status": "completed",
                "split": selected_split,
                "rows_requested": rows_requested,
                "rows_used": int(len(sample_df)),
                "file": out_path.name,
                "error": "",
            }
        )
        return shap_info
    except Exception as exc:  # noqa: BLE001
        logger.exception("SHAP summary generation failed: %s", exc)
        shap_info["status"] = "failed"
        shap_info["error"] = str(exc)
        return shap_info
    finally:
        shap_info["elapsed_seconds"] = float(time.time() - start_ts)


# ── 数据加载 ──────────────────────────────────────────────────────────────────
_MARKET_PARQUET_FILES: dict[str, str] = {
    "HK": "model_features_hk.parquet",
    "US": "model_features_us.parquet",
    "CRYPTO": "model_features_crypto.parquet",
}


def load_data(
    train_start: str,
    train_end: str,
    features: list[str],
    target_horizon_days: int = 1,
    cache_dir: str | None = None,
    valid_end: str | None = None,
    test_end: str | None = None,
    source_mode: str = "LOCAL",
    local_dir: str | None = None,
    market: str = "CN",
) -> tuple:
    local_root = Path(local_dir).expanduser() if local_dir else None
    if local_root is None:
        raise RuntimeError("local_dir must be provided; COS data download has been removed")

    market_upper = str(market or "CN").upper()

    # 仅读取训练必需列，避免整表加载导致 OOM
    horizon = max(1, int(target_horizon_days or 1))
    horizon_col = f"mom_ret_{horizon}d"
    required_columns = list(
        dict.fromkeys(
            ["trade_date", "symbol", "mom_ret_1d", horizon_col, "is_st"] + list(features)
        )
    )
    logger.info(
        "Memory-optimized read: selected %d columns (horizon=%s, market=%s)",
        len(required_columns),
        horizon,
        market_upper,
    )

    # 给标签构建预留边界，避免裁剪过早影响 shift/rolling
    range_start = pd.Timestamp(train_start) - pd.Timedelta(days=max(7, horizon + 3))
    upper_bound = test_end or valid_end or train_end
    range_end = pd.Timestamp(upper_bound) + pd.Timedelta(days=max(7, horizon + 3))

    if market_upper in _MARKET_PARQUET_FILES:
        # ── 非 A 股市场：从单一 parquet 文件加载 ──
        parquet_name = _MARKET_PARQUET_FILES[market_upper]
        parquet_path = local_root / parquet_name
        if not parquet_path.exists():
            raise RuntimeError(
                f"市场 {market_upper} parquet 文件不存在: {parquet_path}"
            )
        logger.info("Loading market-specific parquet: %s", parquet_path)

        # 非 A 股文件使用 'instrument' 列而非 'symbol'
        # 先检查 parquet schema，过滤掉不存在的列（如 mom_ret_2d）
        schema_cols = set(pq.ParquetFile(parquet_path).schema_arrow.names)
        # symbol/instrument 列名兼容
        has_symbol = "symbol" in schema_cols
        has_instrument = "instrument" in schema_cols
        valid_cols = []
        missing_cols = []
        for c in required_columns:
            if c in schema_cols:
                valid_cols.append(c)
            elif c == "symbol" and has_instrument:
                valid_cols.append("instrument")
            else:
                missing_cols.append(c)
        if missing_cols:
            logger.warning("Columns not in parquet (skipped): %s", missing_cols)

        try:
            df = pd.read_parquet(parquet_path, columns=valid_cols, engine="pyarrow")
        except Exception:
            df = pd.read_parquet(parquet_path, columns=valid_cols, engine="pyarrow")
        if "instrument" in df.columns and "symbol" not in df.columns:
            df = df.rename(columns={"instrument": "symbol"})

        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df = df[df["trade_date"].notna()].copy()
        # 日期裁剪
        mask = (df["trade_date"] >= range_start) & (df["trade_date"] <= range_end)
        df = df.loc[mask].copy()
        logger.info("Market %s raw data: %d rows, date range: %s to %s",
                     market_upper, len(df),
                     df["trade_date"].min() if not df.empty else "N/A",
                     df["trade_date"].max() if not df.empty else "N/A")
    else:
        # ── A 股：从年度 parquet 文件加载 ──
        start_year = pd.Timestamp(train_start).year
        ends = [train_end]
        if valid_end: ends.append(valid_end)
        if test_end: ends.append(test_end)
        end_year = max(pd.Timestamp(e).year for e in ends)

        chunks = []
        for year in range(max(start_year - 1, 2016), end_year + 1):
            df_year = _load_local_parquet(
                local_root,
                year,
                required_columns=required_columns,
                clip_start=range_start,
                clip_end=range_end,
            )
            if df_year is not None:
                if not df_year.empty:
                    chunks.append(df_year)
            else:
                logger.warning(f"No data file found for year {year} in {local_root}, skipping")

        if not chunks:
            raise RuntimeError("No data loaded from local storage")

        df = pd.concat(chunks, axis=0, ignore_index=True)
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df = df[df["trade_date"].notna()].copy()
        logger.info(f"Raw concat size: {len(df)} rows. Date range: {df['trade_date'].min()} to {df['trade_date'].max()}")

        # 过滤北交所代码（4/8开头）——仅 A 股
        df["symbol"] = df["symbol"].astype(str).str.zfill(6)
        df = df[~df["symbol"].str.startswith(("4", "8"))].copy()
        logger.info(f"After symbol filter: {len(df)} rows")

        # 过滤 ST/*ST 股票
        if "is_st" in df.columns:
            before = len(df)
            df["is_st"] = pd.to_numeric(df["is_st"], errors="coerce").fillna(0).astype(int)
            df = df[df["is_st"] == 0].copy()
            logger.info(f"After ST filter: {len(df)} rows (removed {before - len(df)} ST rows)")

    # 标签：基于 target_horizon_days 构建 N 日远期收益
    if "mom_ret_1d" not in df.columns:
        raise RuntimeError("Column 'mom_ret_1d' not found in parquet")

    # 从参数读取预测周期（不依赖全局 cfg）
    _horizon = max(1, int(target_horizon_days or 1))

    df = df.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    # 优先使用 parquet 内置的 N 日收益特征（精确复权），否则用累积 shift
    _mom_col = f"mom_ret_{_horizon}d"
    if _horizon == 1:
        df["label"] = df.groupby("symbol")["mom_ret_1d"].shift(-1)
    elif _mom_col in df.columns:
        df["label"] = df.groupby("symbol")[_mom_col].shift(-_horizon)
    else:
        # 回退：通过滚动累乘 1d 收益构造 N 日远期收益
        df["label"] = (
            df.groupby("symbol")["mom_ret_1d"]
            .transform(lambda s: (1 + s).rolling(_horizon).apply(np.prod, raw=True) - 1)
            .shift(-_horizon)
        )
    logger.info(f"Label built with target_horizon_days={_horizon} (column={_mom_col if _mom_col in df.columns else 'rolling'})")

    valid_count_before = len(df)
    df = df[df["label"].notna()].copy()
    logger.info(f"After label shift & dropna: {len(df)} rows (dropped {valid_count_before - len(df)} rows with missing labels)")

    # 裁剪到请求日期范围
    mask = (df["trade_date"] >= train_start) & (df["trade_date"] <= train_end)
    # 如果有验证集/测试集，扩大 mask 范围以包含它们
    if valid_end:
        mask = (df["trade_date"] >= train_start) & (df["trade_date"] <= valid_end)
    if test_end:
        mask = (df["trade_date"] >= train_start) & (df["trade_date"] <= test_end)

    df = df[mask].copy()
    logger.info(f"After date range clip ({train_start} to {test_end or valid_end or train_end}): {len(df)} rows")

    # 校验特征列
    missing = [f for f in features if f not in df.columns]
    if missing:
        logger.warning(f"Features not found in parquet (ignored): {missing}")
        features = [f for f in features if f in df.columns]
    if not features:
        raise RuntimeError("No valid feature columns found")

    keep_cols = ["symbol", "trade_date", "label"] + features
    df = df[keep_cols].reset_index(drop=True)

    # 截面 rank 标准化标签
    df["label"] = df.groupby("trade_date")["label"].rank(pct=True) - 0.5

    logger.info(
        f"Data ready: {len(df):,} rows, {len(features)} features, "
        f"{df['trade_date'].min().date()} ~ {df['trade_date'].max().date()}"
    )
    return df, features


# ── 训练 ──────────────────────────────────────────────────────────────────────

def _split_data(df: pd.DataFrame, cfg: dict) -> tuple:
    """数据切分：显式 split 优先于 val_ratio。返回 (train_df, val_df, test_df)。"""
    model_cfg = cfg.get("model", {})

    def _frame_range_text(frame: pd.DataFrame) -> str:
        if frame.empty:
            return "EMPTY"
        return f"{frame['trade_date'].min().date()}~{frame['trade_date'].max().date()}"

    split_cfg = cfg.get("split", {})
    if split_cfg.get("valid"):
        valid_start_str, valid_end_str = split_cfg["valid"]
        requested_train = f"{split_cfg['train'][0]}~{split_cfg['train'][1]}"
        requested_val = f"{valid_start_str}~{valid_end_str}"
        train_df = df[df["trade_date"] <= pd.Timestamp(split_cfg["train"][1])].copy()
        val_df   = df[
            (df["trade_date"] >= pd.Timestamp(valid_start_str)) &
            (df["trade_date"] <= pd.Timestamp(valid_end_str))
        ].copy()
        if split_cfg.get("test"):
            test_start_str, test_end_str = split_cfg["test"]
            requested_test = f"{test_start_str}~{test_end_str}"
            test_df = df[
                (df["trade_date"] >= pd.Timestamp(test_start_str)) &
                (df["trade_date"] <= pd.Timestamp(test_end_str))
            ].copy()
        else:
            requested_test = requested_val
            test_df = val_df.copy()
        logger.info(f"Split mode: train~{split_cfg['train'][1]}  val {valid_start_str}~{valid_end_str}")
    else:
        val_ratio = float(model_cfg.get("val_ratio") or 0.15)
        dates = sorted(df["trade_date"].unique())
        if not dates:
            raise RuntimeError("No rows available for split after preprocessing. 请检查训练时间窗口与特征快照覆盖范围。")
        val_start = dates[int(len(dates) * (1 - val_ratio))]
        train_df  = df[df["trade_date"] < val_start].copy()
        val_df    = df[df["trade_date"] >= val_start].copy()
        test_df = val_df.copy()
        train_start = pd.Timestamp(df["trade_date"].min()).date()
        train_end = (pd.Timestamp(val_start) - pd.Timedelta(days=1)).date()
        requested_train = f"{train_start}~{train_end}"
        requested_val = f"{pd.Timestamp(val_start).date()}~{pd.Timestamp(df['trade_date'].max()).date()}"
        requested_test = requested_val
        logger.info(
            f"val_ratio mode: train~{pd.Timestamp(val_start).date() - pd.Timedelta(days=1)}"
            f"  val {pd.Timestamp(val_start).date()}~"
        )

    if train_df.empty or val_df.empty or test_df.empty:
        available_range = "EMPTY"
        if not df.empty:
            available_range = f"{df['trade_date'].min().date()}~{df['trade_date'].max().date()}"
        raise RuntimeError(
            "Dataset split contains empty segment. "
            f"available={available_range}; "
            f"train={len(train_df)}({_frame_range_text(train_df)}) requested={requested_train}; "
            f"val={len(val_df)}({_frame_range_text(val_df)}) requested={requested_val}; "
            f"test={len(test_df)}({_frame_range_text(test_df)}) requested={requested_test}. "
            "请调整 train/valid/test 时间窗口，确保三段均与可用数据重叠。"
        )
    return train_df, val_df, test_df


def _prepare_arrays(train_df: pd.DataFrame, val_df: pd.DataFrame, features: list[str]) -> tuple:
    """计算 fill_values 并转换为 numpy 数组。返回 (fill_values, X_train, y_train, X_val, y_val, _fill_fn)。"""
    import math
    fill_values_raw = train_df[features].median().to_dict()
    fill_values = {k: (0.0 if (isinstance(v, float) and math.isnan(v)) else v) for k, v in fill_values_raw.items()}

    def _fill(frame: pd.DataFrame) -> np.ndarray:
        x = frame[features].copy()
        for c in features:
            x[c] = x[c].astype("float32").fillna(fill_values[c])
        return x.to_numpy(dtype=np.float32)

    X_train = _fill(train_df)
    y_train = train_df["label"].astype("float32").to_numpy()
    X_val = _fill(val_df)
    y_val = val_df["label"].astype("float32").to_numpy()
    return fill_values, X_train, y_train, X_val, y_val, _fill


def _train_lgb(cfg: dict, features: list[str], X_train: np.ndarray, y_train: np.ndarray,
               X_val: np.ndarray, y_val: np.ndarray) -> Any:
    """LightGBM 训练。"""
    model_cfg = cfg.get("model", {})
    params = {**DEFAULT_LGB_PARAMS, **model_cfg.get("params", {})}
    num_boost_round = int(model_cfg.get("num_boost_round", 1000))
    early_stopping_rounds = max(1, int(model_cfg.get("early_stopping_rounds", 100) or 100))

    ds_train = lgb.Dataset(X_train, label=y_train, feature_name=features, free_raw_data=True)
    ds_val = lgb.Dataset(X_val, label=y_val, feature_name=features, free_raw_data=True)

    callbacks = [
        lgb.early_stopping(stopping_rounds=early_stopping_rounds, verbose=True),
        lgb.log_evaluation(100),
    ]
    model = lgb.train(
        params, ds_train,
        num_boost_round=num_boost_round,
        valid_sets=[ds_train, ds_val],
        valid_names=["train", "valid"],
        callbacks=callbacks,
    )
    return model


def _train_xgb(cfg: dict, features: list[str], X_train: np.ndarray, y_train: np.ndarray,
               X_val: np.ndarray, y_val: np.ndarray) -> Any:
    """XGBoost 训练。"""
    import xgboost as xgb
    model_cfg = cfg.get("model", {})
    params = {**DEFAULT_XGB_PARAMS, **model_cfg.get("xgb_params", {})}
    num_boost_round = int(model_cfg.get("num_boost_round", 1000))
    early_stopping_rounds = max(1, int(model_cfg.get("early_stopping_rounds", 100) or 100))

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=features)
    dval = xgb.DMatrix(X_val, label=y_val, feature_names=features)

    evals_result: dict = {}
    model = xgb.train(
        params, dtrain,
        num_boost_round=num_boost_round,
        evals=[(dtrain, "train"), (dval, "valid")],
        evals_result=evals_result,
        early_stopping_rounds=early_stopping_rounds,
        verbose_eval=100,
    )
    return model


def _train_catboost(cfg: dict, features: list[str], X_train: np.ndarray, y_train: np.ndarray,
                    X_val: np.ndarray, y_val: np.ndarray) -> Any:
    """CatBoost 训练。"""
    from catboost import CatBoost, Pool
    model_cfg = cfg.get("model", {})
    params = {**DEFAULT_CATBOOST_PARAMS, **model_cfg.get("catboost_params", {})}
    # iterations 覆盖 num_boost_round
    if "iterations" not in model_cfg.get("catboost_params", {}):
        params["iterations"] = int(model_cfg.get("num_boost_round", 1000))

    train_pool = Pool(X_train, label=y_train, feature_names=features)
    val_pool = Pool(X_val, label=y_val, feature_names=features)

    model = CatBoost(params)
    model.fit(train_pool, eval_set=val_pool, early_stopping_rounds=max(1, int(model_cfg.get("early_stopping_rounds", 100) or 100)))
    return model


def _train_linear(cfg: dict, features: list[str], X_train: np.ndarray, y_train: np.ndarray,
                  X_val: np.ndarray, y_val: np.ndarray) -> Any:
    """Linear 模型训练（Ridge 回归）。"""
    from sklearn.linear_model import Ridge
    model_cfg = cfg.get("model", {})
    dl_params = model_cfg.get("dl_params", {})
    alpha = float(dl_params.get("alpha", 1.0))
    model = Ridge(alpha=alpha)
    model.fit(X_train, y_train)
    return model


# ── 深度学习训练 ────────────────────────────────────────────────────────────────

# Qlib TS 模型映射: model_type → (qlib_module, qlib_class)
_QLIB_TS_MODEL_MAP: dict[str, tuple[str, str]] = {
    "gru":         ("qlib.contrib.model.pytorch_gru_ts",         "GRU"),
    "lstm":        ("qlib.contrib.model.pytorch_lstm_ts",        "LSTM"),
    "alstm":       ("qlib.contrib.model.pytorch_alstm_ts",       "ALSTM"),
    "transformer": ("qlib.contrib.model.pytorch_transformer_ts", "Transformer"),
    "tcn":         ("qlib.contrib.model.pytorch_tcn_ts",         "TCN"),
}
_QLIB_FLAT_MODEL_MAP: dict[str, tuple[str, str]] = {
    "tabnet":      ("qlib.contrib.model.pytorch_tabnet",         "TabNet"),
}
_QLIB_MODEL_MAP = {**_QLIB_TS_MODEL_MAP, **_QLIB_FLAT_MODEL_MAP}


class _TSLazyDataset(torch.utils.data.Dataset):
    """Lazy TS dataset: 按需生成滚动窗口，避免一次性加载全部窗口到内存。

    存储原始数据 (per-instrument contiguous arrays)，__getitem__ 时动态切片。
    内存占用: O(total_rows * d_feat) 而非 O(N_windows * step_len * d_feat)。
    """

    def __init__(self, X: np.ndarray, y: np.ndarray, instrument_offsets: list[int], step_len: int):
        self.X = X              # [total_rows, d_feat] float32 contiguous
        self.y = y              # [total_rows] float32
        self.step_len = step_len
        # 每个 instrument 的有效窗口起始行号 (全局索引)
        self.indices: list[int] = []
        for start, end in zip(instrument_offsets[:-1], instrument_offsets[1:]):
            n = end - start
            for i in range(n - step_len + 1):
                self.indices.append(start + i)
        if not self.indices:
            raise ValueError(f"No valid TS samples (step_len={step_len}, rows={len(X)})")

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, idx: int) -> "torch.Tensor":
        import torch
        start = self.indices[idx]
        window = self.X[start : start + self.step_len].copy()  # [step_len, d_feat]
        label = self.y[start + self.step_len - 1]
        # Qlib TS 模型期望: data[:, 0:-1] = features, data[-1, -1] = label
        label_col = np.full((self.step_len, 1), np.float32(0.0))
        label_col[-1, 0] = label
        row = np.concatenate([window, label_col], axis=1)  # [step_len, d_feat+1]
        return torch.from_numpy(row)


def _build_ts_dataloader(
    df_X: pd.DataFrame,
    df_y: pd.Series,
    step_len: int,
    batch_size: int,
    shuffle: bool = True,
) -> "torch.utils.data.DataLoader":
    """将扁平 DataFrame (MultiIndex: instrument x datetime) 转为 3D DataLoader。

    每个样本是 [step_len, d_feat+1]，最后一列为 label (取自最后一个时间步)。
    使用 LazyDataset 按需生成窗口，内存占用 O(rows * d_feat)。
    """
    import torch
    from torch.utils.data import DataLoader

    X_values = np.ascontiguousarray(df_X.values, dtype=np.float32)
    y_values = np.ascontiguousarray(df_y.values, dtype=np.float32)

    if isinstance(df_X.index, pd.MultiIndex):
        instruments = df_X.index.get_level_values(0).unique()
        # 预计算每个 instrument 在连续数组中的 offset
        offsets = [0]
        for inst in instruments:
            mask = df_X.index.get_level_values(0) == inst
            offsets.append(offsets[-1] + int(mask.sum()))
        # 重排为 instrument-连续布局
        order = np.concatenate([np.where(df_X.index.get_level_values(0) == inst)[0] for inst in instruments])
        X_values = X_values[order]
        y_values = y_values[order]
    else:
        offsets = [0, len(X_values)]

    dataset = _TSLazyDataset(X_values, y_values, offsets, step_len)
    logger.info("TS DataLoader: %d samples from %d rows (step_len=%d)", len(dataset), len(X_values), step_len)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, drop_last=False, num_workers=0)


def _train_dl(
    model_type: str,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    features: list[str],
    dl_params: dict[str, Any],
    output_dir: Path,
    hardware: dict[str, Any] | None = None,
) -> tuple:
    """Qlib 深度学习模型训练。

    返回 (model_obj, train_metrics, val_metrics, dl_metadata)
    """
    import importlib
    import copy
    import torch

    mod_path, cls_name = _QLIB_MODEL_MAP[model_type]
    mod = importlib.import_module(mod_path)
    ModelCls = getattr(mod, cls_name)

    d_feat = len(features)
    is_ts = model_type in _QLIB_TS_MODEL_MAP

    # 构建模型参数
    model_params: dict[str, Any] = {"d_feat": d_feat}
    if model_type == "tabnet":
        model_params.update({
            "n_d":     int(dl_params.get("dl_hidden_size", 64)),
            "n_a":     int(dl_params.get("dl_hidden_size", 64)),
            "n_steps": max(1, int(dl_params.get("dl_num_layers", 3))),
            "lr":      float(dl_params.get("dl_lr", 0.001)),
        })
    else:
        model_params.update({
            "hidden_size": int(dl_params.get("dl_hidden_size", 64)),
            "num_layers":  int(dl_params.get("dl_num_layers", 2)),
            "dropout":     float(dl_params.get("dl_dropout", 0.3)),
        })

    n_epochs    = int(dl_params.get("dl_n_epochs", 200))
    batch_size  = int(dl_params.get("dl_batch_size", 2000))
    lr          = float(dl_params.get("dl_lr", 0.001))
    step_len    = int(dl_params.get("dl_step_len", 20))
    early_stop  = int(dl_params.get("early_stopping_rounds", 20))
    metric_name = str(dl_params.get("metric", "")).lower()

    # 确定 GPU
    gpu_id = 0
    if hardware and not hardware.get("gpu_available"):
        gpu_id = -1
    model_params["GPU"] = gpu_id
    model_params["n_epochs"] = n_epochs
    model_params["lr"] = lr
    model_params["batch_size"] = batch_size
    model_params["early_stop"] = early_stop
    model_params["metric"] = metric_name

    logger.info("DL model: %s, params=%s, is_ts=%s", model_type, model_params, is_ts)

    # 实例化模型
    model_obj = ModelCls(**model_params)

    # 准备训练/验证数据
    X_train = train_df[features]
    y_train = train_df["label"]
    X_val = val_df[features]
    y_val = val_df["label"]

    if is_ts:
        train_loader = _build_ts_dataloader(X_train, y_train, step_len, batch_size, shuffle=True)
        val_loader = _build_ts_dataloader(X_val, y_val, step_len, batch_size, shuffle=False)
        logger.info("TS DataLoader: train_batches=%d, val_batches=%d, step_len=%d",
                     len(train_loader), len(val_loader), step_len)
    else:
        # TabNet: 使用扁平数据
        train_loader = (X_train, y_train)
        val_loader = (X_val, y_val)

    # 训练循环 (直接调用 Qlib 模型的 train_epoch/test_epoch)
    best_score = -np.inf
    best_epoch = 0
    stop_steps = 0
    best_state = None
    evals: dict[str, list[float]] = {"train": [], "valid": []}

    logger.info("DL training: %d epochs, batch_size=%d, lr=%s", n_epochs, batch_size, lr)

    for epoch in range(n_epochs):
        # Train
        model_obj.train_epoch(train_loader) if is_ts else model_obj.train_epoch(X_train, y_train)

        # Evaluate
        if is_ts:
            train_loss, train_score = model_obj.test_epoch(train_loader)
            val_loss, val_score = model_obj.test_epoch(val_loader)
        else:
            train_loss, train_score = model_obj.test_epoch(X_train, y_train)
            val_loss, val_score = model_obj.test_epoch(X_val, y_val)

        evals["train"].append(train_score)
        evals["valid"].append(val_score)

        if (epoch + 1) % 10 == 0 or epoch == 0:
            logger.info("Epoch %d/%d: train=%.6f, valid=%.6f", epoch + 1, n_epochs, train_score, val_score)

        if val_score > best_score:
            best_score = val_score
            best_epoch = epoch
            stop_steps = 0
            # 保存最佳状态
            inner_model = getattr(model_obj, "model", None)
            if inner_model is None:
                for attr_name in ("gru_model", "lstm_model", "alstm_model", "transformer_model", "tcn_model", "tabnet_model"):
                    inner_model = getattr(model_obj, attr_name, None)
                    if inner_model is not None:
                        break
            if inner_model is not None:
                best_state = copy.deepcopy(inner_model.state_dict())
        else:
            stop_steps += 1
            if stop_steps >= early_stop:
                logger.info("Early stop at epoch %d (best=%d, score=%.6f)", epoch, best_epoch, best_score)
                break

    # 恢复最佳模型
    if best_state is not None:
        inner_model = getattr(model_obj, "model", None)
        if inner_model is None:
            for attr_name in ("gru_model", "lstm_model", "alstm_model", "transformer_model", "tcn_model", "tabnet_model"):
                inner_model = getattr(model_obj, attr_name, None)
                if inner_model is not None:
                    break
        if inner_model is not None:
            inner_model.load_state_dict(best_state)

    # 保存模型
    torch.save(best_state, str(output_dir / "model.pth"))
    logger.info("DL model saved: model.pth (best_epoch=%d, best_score=%.6f)", best_epoch, best_score)

    # 计算指标
    train_m = {"ic": evals["train"][best_epoch] if evals["train"] else float("nan"), "rank_ic": float("nan"), "rank_icir": float("nan"), "rmse": float("nan"), "auc": float("nan")}
    val_m = {"ic": evals["valid"][best_epoch] if evals["valid"] else float("nan"), "rank_ic": float("nan"), "rank_icir": float("nan"), "rmse": float("nan"), "auc": float("nan")}

    # DL 元数据 (供推理重建模型)
    dl_metadata = {
        "model_class_name": cls_name,
        "model_params": {k: v for k, v in model_params.items() if k not in ("GPU", "n_epochs", "lr", "batch_size", "early_stop", "metric")},
        "is_sequence_model": is_ts,
        "input_spec": {
            "tensor_shape": [None, step_len, d_feat] if is_ts else [None, d_feat],
            "feature_columns": features,
        },
        "dl_params": {k: v for k, v in dl_params.items()},
    }

    return model_obj, train_m, val_m, dl_metadata


def _predict_dl(
    model_dir: Path,
    df_X: pd.DataFrame,
    features: list[str],
    dl_metadata: dict[str, Any],
    batch_size: int = 2000,
) -> np.ndarray:
    """加载训练好的 DL 模型并预测。"""
    import importlib
    import torch

    cls_name = dl_metadata.get("model_class_name", "")
    model_params = dl_metadata.get("model_params", {})
    is_ts = dl_metadata.get("is_sequence_model", False)

    # 找到对应的 Qlib 模型类
    model_cls = None
    for _map in (_QLIB_TS_MODEL_MAP, _QLIB_FLAT_MODEL_MAP):
        for _mt, (_mod_path, _cls_name) in _map.items():
            if _cls_name == cls_name:
                mod = importlib.import_module(_mod_path)
                model_cls = getattr(mod, _cls_name)
                break
        if model_cls is not None:
            break

    if model_cls is None:
        raise ValueError(f"Cannot find Qlib model class: {cls_name}")

    model_params["GPU"] = -1  # CPU for inference
    model_obj = model_cls(**model_params)

    # 加载权重
    model_path = model_dir / "model.pth"
    if not model_path.exists():
        raise FileNotFoundError(f"model.pth not found at {model_path}")

    state_dict = torch.load(str(model_path), map_location="cpu")
    inner_model = getattr(model_obj, "model", None)
    if inner_model is None:
        for attr_name in ("gru_model", "lstm_model", "alstm_model", "transformer_model", "tcn_model", "tabnet_model"):
            inner_model = getattr(model_obj, attr_name, None)
            if inner_model is not None:
                break
    if inner_model is not None:
        inner_model.load_state_dict(state_dict)
    model_obj.fitted = True

    # 预测
    if is_ts:
        step_len = dl_metadata.get("dl_params", {}).get("dl_step_len", 20)
        loader = _build_ts_dataloader(df_X[features], pd.Series(0.0, index=df_X.index), step_len, batch_size, shuffle=False)
        model_obj.model.eval() if hasattr(model_obj, "model") else None
        preds = []
        for (data,) in loader:
            feature = data[:, :, 0:-1]
            with torch.no_grad():
                if hasattr(model_obj, "model") and model_obj.model is not None:
                    pred = model_obj.model(feature.float()).detach().cpu().numpy()
                else:
                    pred = model_obj.predict(feature.float()).detach().cpu().numpy()
            preds.append(pred)
        return np.concatenate(preds)
    else:
        X_values = df_X[features].values.astype(np.float32)
        X_tensor = torch.from_numpy(X_values)
        model_obj.model.eval() if hasattr(model_obj, "model") else None
        preds = []
        for i in range(0, len(X_tensor), batch_size):
            batch = X_tensor[i:i+batch_size]
            with torch.no_grad():
                priors = torch.ones(batch.shape[0], len(features))
                pred = model_obj.model(batch, priors).detach().cpu().numpy()
            preds.append(pred)
        return np.concatenate(preds)


def _predict_with_model(model: Any, X: np.ndarray, model_type: str, features: list[str] | None = None) -> np.ndarray:
    """统一预测接口，适配不同框架。"""
    if model_type == "lightgbm":
        return model.predict(X, num_iteration=model.best_iteration)
    elif model_type == "xgboost":
        import xgboost as xgb
        dmat = xgb.DMatrix(X, feature_names=features)
        return model.predict(dmat, iteration_range=(0, model.best_iteration + 1))
    elif model_type == "catboost":
        return model.predict(X)
    elif model_type == "linear":
        return model.predict(X)
    else:
        return model.predict(X)


def _save_model(model: Any, model_type: str, out_dir: Path) -> str:
    """保存模型到文件，返回实际文件名。"""
    if model_type == "lightgbm":
        path = out_dir / "model.lgb"
        model.save_model(str(path))
        return "model.lgb"
    elif model_type == "xgboost":
        path = out_dir / "model.xgb"
        model.save_model(str(path))
        return "model.xgb"
    elif model_type == "catboost":
        path = out_dir / "model.cbm"
        model.save_model(str(path), format="cbm")
        return "model.cbm"
    elif model_type == "linear":
        import pickle
        path = out_dir / "model.pkl"
        with open(path, "wb") as f:
            pickle.dump(model, f)
        return "model.pkl"
    elif model_type in _DL_MODEL_TYPES:
        # DL 模型在 _train_dl() 中已保存 model.pth，此处仅返回文件名
        return "model.pth"
    else:
        import pickle
        path = out_dir / "model.pkl"
        with open(path, "wb") as f:
            pickle.dump(model, f)
        return "model.pkl"


def _get_model_framework(model_type: str) -> str:
    """返回模型框架名。"""
    mapping = {
        "lightgbm": "lightgbm",
        "xgboost": "xgboost",
        "catboost": "catboost",
        "linear": "sklearn",
        "gru": "pytorch",
        "lstm": "pytorch",
        "alstm": "pytorch",
        "transformer": "pytorch",
        "tra": "pytorch",
        "hist": "pytorch",
        "tabnet": "pytorch",
        "tcn": "pytorch",
    }
    return mapping.get(model_type, "unknown")


def train_model(df: pd.DataFrame, features: list[str], cfg: dict, hardware: dict | None = None) -> tuple:
    """统一训练入口：根据 model_type 路由到对应训练函数。"""
    model_cfg = cfg.get("model", {})
    model_type = str(model_cfg.get("type", "lightgbm")).strip().lower()

    if model_type not in _ALL_MODEL_TYPES:
        raise ValueError(f"Unsupported model_type: {model_type}")

    # 检查深度学习模型是否有 GPU
    if model_type in _DL_MODEL_TYPES and hardware and not hardware.get("gpu_available"):
        logger.warning("DL model '%s' requested but no GPU detected. Training will be slow on CPU.", model_type)

    # 数据切分
    train_df, val_df, test_df = _split_data(df, cfg)
    fill_values, X_train, y_train, X_val, y_val, _fill = _prepare_arrays(train_df, val_df, features)

    # 路由到对应训练函数
    logger.info("Training model: %s (framework=%s)", model_type, _get_model_framework(model_type))
    train_t0 = time.time()

    if model_type == "lightgbm":
        model = _train_lgb(cfg, features, X_train, y_train, X_val, y_val)
    elif model_type == "xgboost":
        model = _train_xgb(cfg, features, X_train, y_train, X_val, y_val)
    elif model_type == "catboost":
        model = _train_catboost(cfg, features, X_train, y_train, X_val, y_val)
    elif model_type == "linear":
        model = _train_linear(cfg, features, X_train, y_train, X_val, y_val)
    elif model_type in _DL_MODEL_TYPES:
        dl_params = model_cfg.get("dl_params", {})
        output_dir = Path("/workspace")
        model, train_m, val_m, dl_metadata = _train_dl(
            model_type, train_df, val_df, features, dl_params, output_dir, hardware=hardware
        )
        train_elapsed = time.time() - train_t0
        logger.info("Training finished in %.2fs (%s)", train_elapsed, model_type)
        logger.info(f"Val IC={val_m['ic']:.4f}")

        # DL 模型生成全窗口预测
        y_full_pred = _predict_dl(output_dir, df, features, dl_metadata)
        full_pred_df = df[["symbol", "trade_date", "label"]].copy()
        full_pred_df["pred"] = y_full_pred
        full_pred_df["split"] = "train"
        full_pred_df.loc[
            (full_pred_df["trade_date"] >= val_df["trade_date"].min()) &
            (full_pred_df["trade_date"] <= val_df["trade_date"].max()),
            "split",
        ] = "valid"
        full_pred_df.loc[
            (full_pred_df["trade_date"] >= test_df["trade_date"].min()) &
            (full_pred_df["trade_date"] <= test_df["trade_date"].max()),
            "split",
        ] = "test"

        # 计算 test 集指标
        test_mask = full_pred_df["split"] == "test"
        y_test_pred = full_pred_df.loc[test_mask, "pred"].values
        y_test_true = full_pred_df.loc[test_mask, "label"].values
        test_m = _compute_metrics(test_df, y_test_true.astype("float32"), y_test_pred.astype("float32"))

        return (
            model,
            fill_values,
            train_m,
            val_m,
            test_m,
            full_pred_df.reset_index(drop=True),
            {
                "train": train_df.reset_index(drop=True),
                "valid": val_df.reset_index(drop=True),
                "test": test_df.reset_index(drop=True),
            },
            model_type,
            dl_metadata,
        )
    else:
        raise ValueError(f"Unsupported model_type: {model_type}")

    train_elapsed = time.time() - train_t0
    logger.info("Training finished in %.2fs (%s)", train_elapsed, model_type)

    # 统一预测 (树模型)
    y_train_pred = _predict_with_model(model, _fill(train_df), model_type, features)
    y_val_pred = _predict_with_model(model, _fill(val_df), model_type, features)
    y_test_pred = _predict_with_model(model, _fill(test_df), model_type, features)
    train_m = _compute_metrics(train_df, y_train, y_train_pred)
    val_m   = _compute_metrics(val_df,   y_val,   y_val_pred)
    test_m  = _compute_metrics(test_df,  test_df["label"].astype("float32").to_numpy(), y_test_pred)

    logger.info(f"Train IC={train_m['ic']:.4f}  RankIC={train_m['rank_ic']:.4f}")
    logger.info(f"Val   IC={val_m['ic']:.4f}    RankIC={val_m['rank_ic']:.4f}  ICIR={val_m['rank_icir']:.4f}")

    # 生成全窗口预测
    full_pred_df = df[["symbol", "trade_date", "label"]].copy()
    full_pred_df["pred"] = _predict_with_model(model, _fill(df), model_type, features)
    full_pred_df["split"] = "train"
    full_pred_df.loc[
        (full_pred_df["trade_date"] >= val_df["trade_date"].min()) &
        (full_pred_df["trade_date"] <= val_df["trade_date"].max()),
        "split",
    ] = "valid"
    full_pred_df.loc[
        (full_pred_df["trade_date"] >= test_df["trade_date"].min()) &
        (full_pred_df["trade_date"] <= test_df["trade_date"].max()),
        "split",
    ] = "test"
    return (
        model,
        fill_values,
        train_m,
        val_m,
        test_m,
        full_pred_df.reset_index(drop=True),
        {
            "train": train_df.reset_index(drop=True),
            "valid": val_df.reset_index(drop=True),
            "test": test_df.reset_index(drop=True),
        },
        model_type,
    )


# ── 主入口 ────────────────────────────────────────────────────────────────────
def main() -> int:
    # 最早期诊断日志：在任何处理之前打印，确保 Batch 环境中一定能看到
    print(f"[BOOT] python={sys.version}", flush=True)
    print(f"[BOOT] argv={sys.argv}", flush=True)

    parser = argparse.ArgumentParser(description="QuantMind Training — YAML config driven")
    parser.add_argument("--config", required=False, help="Path to config.yaml")
    try:
        args, unknown_args = parser.parse_known_args()
    except SystemExit as exc:
        if int(getattr(exc, "code", 1) or 0) == 0:
            return 0
        # Batch 运行时偶发注入畸形参数（如缺失值的已知 flag）会触发 argparse 退出码 2。
        # 这里降级为环境变量驱动启动，避免任务在入口阶段直接失败。
        logger.warning(f"Argparse failed with argv={sys.argv}; fallback to env-driven args")
        args = argparse.Namespace(config=None)
        unknown_args = []
    if unknown_args:
        logger.warning(f"Ignoring unknown CLI args from runtime: {unknown_args}")

    # 本地挂载 config.yaml，CLI 参数作为可选覆盖
    cfg_path = Path(args.config) if args.config else Path("/tmp/config.yaml")

    run_id     = "unknown"
    result: dict = {}
    callback_url    = ""
    callback_secret = ""
    result_path = Path("/workspace/result.json")

    try:
        if not cfg_path.exists():
            raise RuntimeError(f"Config file not found: {cfg_path}")
        cfg = yaml.safe_load(cfg_path.read_text())

        run_id          = cfg.get("run_id", "unknown")
        job_name        = cfg.get("job_name", "unnamed")
        result_path     = Path(cfg.get("output", {}).get("result_path", "/workspace/result.json"))
        callback_url    = cfg.get("callback", {}).get("url", "")
        callback_secret = cfg.get("callback", {}).get("secret", "")

        logger.info("=== QuantMind Training Start ===")
        logger.info(f"run_id={run_id}  job={job_name}  config={cfg_path}")

        # 硬件环境检测
        hardware = detect_hardware()

        # 数据加载（特征列自动补齐基础6列）
        submitted_features = list(dict.fromkeys([str(item).strip() for item in (cfg["data"].get("features", []) or []) if str(item).strip()]))
        auto_appended_features = [feature for feature in TRAINING_BASE_FEATURES if feature not in submitted_features]
        features = list(dict.fromkeys(TRAINING_BASE_FEATURES + submitted_features))
        source_mode = str((cfg.get("data", {}) or {}).get("source_mode") or "LOCAL").strip().upper()
        local_data_dir = str((cfg.get("data", {}) or {}).get("local_dir") or "").strip() or None
        explain_cfg = _normalize_explain_cfg(cfg.get("explain") or {})
        context_cfg = cfg.get("context", {}) or {}
        market = str(context_cfg.get("market", "CN")).upper()

        df, valid_features = load_data(
            cfg["data"]["train_start"],
            cfg["data"]["train_end"],
            features,
            target_horizon_days=int((cfg.get("label", {}) or {}).get("target_horizon_days") or 1),
            cache_dir=cfg.get("cache", {}).get("dir"),
            valid_end=cfg.get("split", {}).get("valid", [None, None])[1],
            test_end=cfg.get("split", {}).get("test", [None, None])[1],
            source_mode=source_mode,
            local_dir=local_data_dir,
            market=market,
        )
        train_t0 = time.time()
        train_result = train_model(df, valid_features, cfg, hardware=hardware)
        # train_model 返回 8-tuple (树模型) 或 9-tuple (DL 模型，含 dl_metadata)
        if len(train_result) == 9:
            model, fill_values, train_m, val_m, test_m, pred_df, split_frames, actual_model_type, dl_metadata = train_result
        else:
            model, fill_values, train_m, val_m, test_m, pred_df, split_frames, actual_model_type = train_result
            dl_metadata = None
        elapsed = float(time.time() - train_t0)

        # 获取 best_iteration（不同框架方式不同）
        best_iteration = getattr(model, "best_iteration", None)
        if best_iteration is None and hasattr(model, "get_best_iteration"):
            try:
                best_iteration = model.get_best_iteration()
            except Exception:
                best_iteration = None
        logger.info("Training finished in %.2fs, best_iteration=%s, model_type=%s", elapsed, best_iteration, actual_model_type)

        # 保存模型（多框架）
        workspace = Path("/workspace")
        model_filename = _save_model(model, actual_model_type, workspace)
        logger.info(f"Model saved to {workspace / model_filename}")

        # 保存预测结果（parquet 压缩用于存档，比 pickle 小 ~10x）
        pred_path = Path("/workspace/pred.parquet")
        pred_df.to_parquet(pred_path, engine="pyarrow", compression="zstd", index=False)
        logger.info(f"Predictions saved to {pred_path} ({pred_path.stat().st_size/1024/1024:.1f} MB)")

        # 同时保存回测引擎兼容格式 pred.pkl
        # 回测引擎要求: MultiIndex(datetime, instrument) + 'score' 列
        pred_qlib = (
            pred_df[["trade_date", "symbol", "pred"]]
            .rename(columns={"trade_date": "datetime", "symbol": "instrument", "pred": "score"})
            .assign(datetime=lambda d: pd.to_datetime(d["datetime"]))
            .set_index(["datetime", "instrument"])
            .sort_index()
        )
        pred_pkl_path = Path("/workspace/pred.pkl")
        pred_qlib.to_pickle(pred_pkl_path)
        logger.info(f"Backtest-compatible pred.pkl saved ({pred_pkl_path.stat().st_size/1024/1024:.1f} MB, {len(pred_qlib):,} rows)")

        shap_summary_path = Path("/workspace/shap_summary.csv")
        # SHAP: pred_contrib 仅支持 LightGBM；其他框架暂跳过
        if actual_model_type != "lightgbm":
            explain_cfg_shap = {**explain_cfg, "enable_shap": False}
            logger.info("SHAP disabled: pred_contrib not supported for %s", actual_model_type)
        else:
            explain_cfg_shap = explain_cfg
        shap_info = _compute_shap_summary(
            model=model,
            split_frames=split_frames,
            features=valid_features,
            fill_values=fill_values,
            explain_cfg=explain_cfg_shap,
            out_path=shap_summary_path,
        )
        if shap_info.get("status") == "completed":
            logger.info(
                "SHAP summary generated: split=%s rows=%s -> %s",
                shap_info.get("split"),
                shap_info.get("rows_used"),
                shap_summary_path,
            )
        elif shap_info.get("status") == "disabled":
            logger.info("SHAP summary disabled by config")
        elif shap_info.get("status") == "skipped":
            logger.warning("SHAP summary skipped: %s", shap_info.get("error") or "unknown")
        else:
            logger.warning("SHAP summary failed: %s", shap_info.get("error") or "unknown")

        # 构造 metadata
        metadata = {
            "run_id": run_id, "job_name": job_name,
            "framework": _get_model_framework(actual_model_type),
            "model_type": actual_model_type,
            "model_file": model_filename,
            "hardware": hardware,
            "feature_count": len(valid_features),
            "requested_feature_count": len(submitted_features),
            "requested_features": submitted_features,
            "auto_appended_feature_count": len(auto_appended_features),
            "auto_appended_features": auto_appended_features,
            "features": valid_features,
            "feature_columns": valid_features,
            "fill_values": fill_values,
            "train_start": cfg["data"]["train_start"],
            "train_end":   cfg["data"]["train_end"],
            "val_start":   (cfg.get("split", {}).get("valid") or [None, None])[0] or "",
            "val_end":     (cfg.get("split", {}).get("valid") or [None, None])[1] or "",
            "test_start":  (cfg.get("split", {}).get("test")  or [None, None])[0] or "",
            "test_end":    (cfg.get("split", {}).get("test")  or [None, None])[1] or "",
            "data_source": "parquet",
            "context": context_cfg,
            "best_iteration": best_iteration,
            "target_horizon_days": int((cfg.get("label", {}) or {}).get("target_horizon_days") or 1),
            "target_mode": str((cfg.get("label", {}) or {}).get("target_mode") or "return"),
            "label_formula": str((cfg.get("label", {}) or {}).get("label_formula") or ""),
            "effective_trade_date": str((cfg.get("label", {}) or {}).get("effective_trade_date") or ""),
            "training_window": str((cfg.get("label", {}) or {}).get("training_window") or ""),
            "metrics": {
                "train_ic": train_m["ic"], "train_rank_ic": train_m["rank_ic"], "train_rank_icir": train_m["rank_icir"],
                "val_ic": val_m["ic"], "val_rank_ic": val_m["rank_ic"], "val_rank_icir": val_m["rank_icir"],
                "test_ic": test_m["ic"], "test_rank_ic": test_m["rank_ic"], "test_rank_icir": test_m["rank_icir"],
            },
            "pred_coverage_start": str(pred_df["trade_date"].min().date()) if not pred_df.empty else "",
            "pred_coverage_end": str(pred_df["trade_date"].max().date()) if not pred_df.empty else "",
            "pred_rows": int(len(pred_df)),
            "shap": shap_info,
            "generated_at": datetime.utcnow().isoformat(),
            "elapsed_seconds": elapsed,
        }
        # DL 模型特有元数据 (model_class_name, model_params, input_spec 等)
        if dl_metadata:
            metadata.update(dl_metadata)
        def _sanitize_for_json_meta(obj):
            import math
            if isinstance(obj, dict):
                return {k: _sanitize_for_json_meta(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_sanitize_for_json_meta(v) for v in obj]
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            return obj

        metadata_bytes = json.dumps(_sanitize_for_json_meta(metadata), ensure_ascii=False, indent=2).encode()
        Path("/workspace/metadata.json").write_bytes(metadata_bytes)
        logger.info("metadata.json saved locally")

        # 复制统一推理脚本模板（而非内联生成旧版脚本）
        template_path = Path("/app/backend/services/engine/inference/templates/inference_parquet.py")
        inference_dest = Path("/workspace/inference.py")
        if template_path.is_file():
            inference_dest.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
            logger.info("inference.py copied from unified template: %s", template_path)
        else:
            # 兜底：模板不存在时写入简化版（仅记录警告）
            logger.warning("统一推理模板不存在: %s，使用简化版", template_path)
            _INFERENCE_SCRIPT_FALLBACK = '''#!/usr/bin/env python3
"""
QuantMind Parquet 数据源推理脚本 (inference.py 模板)
=====================================================
适用于训练数据来自 feature_snapshots/*.parquet 的 LightGBM 模型。

平台注入环境变量：
    MODEL_DIR      模型目录绝对路径（含 metadata.json + model.lgb）
    TRADE_DATE     推理日期（同 --date 参数，互为备份）
    OUTPUT_FORMAT  固定值 json

调用方式（由 InferenceScriptRunner 自动调用）：
    python inference.py --date YYYY-MM-DD --output /path/to/out.json

输出格式（写入 --output 文件）：
    [{"symbol": "sh600519", "score": 0.82}, ...]

exit code：
    0  = 成功
    1  = 致命错误（模型/元数据损坏）
    2  = 该日期无可用数据（触发 alpha158 兜底）
"""
from __future__ import annotations
import argparse, json, logging, os, sys
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger("inference_parquet")

_DEFAULT_DATA_DIR = "/app/db/feature_snapshots"

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--date", "-d", type=str, default=os.getenv("TRADE_DATE", ""))
    p.add_argument("--output", "-o", type=str, required=True)
    p.add_argument("--model-dir", type=str, default=os.getenv("MODEL_DIR", str(Path(__file__).parent)))
    p.add_argument("--data-dir", type=str, default=os.getenv("MODEL_TRAINING_DATA_DIR", _DEFAULT_DATA_DIR))
    return p.parse_args()

def load_metadata(model_dir):
    meta_path = Path(model_dir) / "metadata.json"
    if not meta_path.exists():
        logger.error("metadata.json 不存在: %s", meta_path); sys.exit(1)
    return json.loads(meta_path.read_text(encoding="utf-8"))

def load_model(model_dir, meta):
    model_path = Path(model_dir) / meta.get("model_file", "model.lgb")
    if not model_path.exists():
        candidates = list(Path(model_dir).glob("*.lgb")) + list(Path(model_dir).glob("*.txt"))
        if not candidates:
            logger.error("未找到 LightGBM 模型文件: %s", model_dir); sys.exit(1)
        model_path = candidates[0]
    logger.info("加载模型: %s", model_path.name)
    return lgb.Booster(model_file=str(model_path))

_MARKET_PARQUET = {"HK": "model_features_hk.parquet", "US": "model_features_us.parquet", "CRYPTO": "model_features_crypto.parquet"}

def load_date_data(trade_date, data_dir, meta):
    market = str((meta.get("context") or {}).get("market", "")).upper()
    if market in _MARKET_PARQUET:
        parquet_path = Path(data_dir) / _MARKET_PARQUET[market]
    else:
        year = int(trade_date[:4])
        parquet_path = Path(data_dir) / f"model_features_{year}.parquet"
    if not parquet_path.exists():
        logger.warning("parquet 文件不存在: %s", parquet_path); return None
    df = pd.read_parquet(parquet_path, engine="pyarrow")
    if "symbol" not in df.columns and "instrument" in df.columns:
        df = df.rename(columns={"instrument": "symbol"})
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    day_df = df[df["trade_date"] == trade_date].copy()
    if len(day_df) == 0:
        logger.warning("日期 %s 无数据", trade_date); return None
    logger.info("找到 %d 条记录，日期=%s", len(day_df), trade_date)
    return day_df

def preprocess(df, meta):
    feature_cols = meta.get("feature_columns") or meta.get("features", [])
    fill_values  = meta.get("fill_values", {})
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        logger.warning("缺少 %d 个特征列，填 0: %s", len(missing), missing[:8])
        for c in missing: df[c] = 0.0
    X_df = df[feature_cols].copy()
    for col, val in fill_values.items():
        if col in X_df.columns: X_df[col] = X_df[col].fillna(val)
    return X_df.fillna(0.0), df["symbol"].tolist()

def main():
    args = parse_args()
    trade_date = (args.date or "").strip()
    if not trade_date:
        logger.error("未指定推理日期"); sys.exit(1)
    model_dir, data_dir, out_path = Path(args.model_dir), Path(args.data_dir), Path(args.output)
    logger.info("=== parquet 推理脚本 === date=%s  model_dir=%s", trade_date, model_dir)
    meta  = load_metadata(model_dir)
    day_df = load_date_data(trade_date, data_dir, meta)
    if day_df is None:
        print(f"日期 {trade_date} 无数据，触发兜底", file=sys.stderr); sys.exit(2)
    model = load_model(model_dir, meta)
    X_df, symbols = preprocess(day_df, meta)
    if len(X_df) == 0:
        print(f"日期 {trade_date} 预处理后无有效行", file=sys.stderr); sys.exit(2)
    scores = model.predict(X_df.values.astype(np.float32), num_iteration=meta.get("best_iteration"))
    signals = sorted(
        [{"symbol": s, "score": float(v)} for s, v in zip(symbols, scores) if v == v],
        key=lambda x: x["score"], reverse=True
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(signals, ensure_ascii=False), encoding="utf-8")
    logger.info("已写入信号文件: %s  (%d 条)", out_path, len(signals))

if __name__ == "__main__":
    main()
'''
            inference_dest.write_text(_INFERENCE_SCRIPT_FALLBACK, encoding="utf-8")
            logger.info("inference.py fallback version written to model directory")

        result = {
            "status": "completed",
            "run_id": run_id,
            "job_name": job_name,
            "metrics": {
                "train": {"rmse": train_m["rmse"], "auc": train_m["auc"]},
                "val": {"rmse": val_m["rmse"], "auc": val_m["auc"]},
                "test": {"rmse": test_m["rmse"], "auc": test_m["auc"]},
            },
            "artifacts": [
                {"name": model_filename,  "local": f"/workspace/{model_filename}"},
                {"name": "pred.parquet",  "local": "/workspace/pred.parquet"},
                {"name": "metadata.json", "local": "/workspace/metadata.json"},
                {"name": "inference.py",  "local": "/workspace/inference.py"},
                {"name": "config.yaml",   "local": "/workspace/config.yaml"},
                {"name": "result.json",   "local": "/workspace/result.json"},
            ],
            "summary": {
                "status": "训练完成",
                "message": f"训练完成({actual_model_type})，best_iteration={best_iteration}，产物已保存到本地模型目录",
            },
            "metadata": metadata,
            "error": "",
            "logs": f"val_rmse={val_m['rmse']:.6f}, val_auc={val_m['auc']:.6f}",
        }
        if shap_info.get("status") == "completed" and shap_summary_path.exists():
            result["artifacts"].append({"name": "shap_summary.csv", "local": "/workspace/shap_summary.csv"})

    except Exception as e:
        logger.exception(f"Training failed: {e}")
        result = {"status": "failed", "run_id": run_id, "error": str(e)}

    finally:
        def _sanitize_for_json(obj):
            """Replace NaN/Inf with None for JSON compliance."""
            import math
            if isinstance(obj, dict):
                return {k: _sanitize_for_json(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_sanitize_for_json(v) for v in obj]
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            return obj

        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_clean = _sanitize_for_json(result)
        result_json = json.dumps(result_clean, ensure_ascii=False, indent=2)
        result_path.write_text(result_json)
        logger.info(f"result.json → {result_path}")

        if callback_url:
            try:
                resp = requests.post(
                    callback_url, json=result_clean,
                    headers={"X-Internal-Call-Secret": callback_secret},
                    timeout=15,
                )
                logger.info(f"Callback → HTTP {resp.status_code}")
            except Exception as cb_err:
                logger.warning(f"Callback failed (non-fatal): {cb_err}")

    logger.info("=== Training Complete ===")
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
