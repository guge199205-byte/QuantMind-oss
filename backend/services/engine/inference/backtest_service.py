"""
Rolling Backtest Service — Evaluate model prediction quality across historical dates.

Runs model inference on multiple dates, compares predicted scores against actual
forward returns (mom_ret_{N}d from parquet), and computes standard quant metrics:
IC, IC_IR, hit rate, decile analysis, long-short return.
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .config import PRODUCTION_MODELS_DIR
from .data_loader import get_available_dates, load_date_data, preprocess

# History storage directory
_HISTORY_DIR = Path("/app/db/backtest_history")
from .model_loader import ModelLoader

logger = logging.getLogger(__name__)


def _max_drawdown(cumulative_returns: list[float]) -> float:
    """Compute max drawdown from a cumulative return series."""
    if not cumulative_returns:
        return 0.0
    peak = cumulative_returns[0]
    max_dd = 0.0
    for r in cumulative_returns:
        peak = max(peak, r)
        dd = peak - r
        max_dd = max(max_dd, dd)
    return float(max_dd)


def _group_by_month(results: list[dict]) -> dict[str, float]:
    """Group IC values by month and compute monthly mean."""
    monthly: dict[str, list[float]] = defaultdict(list)
    for r in results:
        month_key = r["date"][:7]  # "2025-07"
        monthly[month_key].append(r["ic"])
    return {k: float(np.mean(v)) for k, v in monthly.items()}


class BacktestService:
    """Evaluate model predictive power via rolling historical backtest."""

    def __init__(self, production_dir: Path | None = None):
        self.production_dir = production_dir or PRODUCTION_MODELS_DIR
        self.model_loader = ModelLoader(self.production_dir, max_models=3)
        self._prev_top_symbols: list[str] = []

    def resolve_model_dir(self, model_id: str) -> Path:
        """Resolve model directory from model_id."""
        # Try direct path first
        direct = self.production_dir / model_id
        if direct.exists() and (direct / "metadata.json").exists():
            return direct

        # Search in user models
        user_models = Path(self.production_dir).parent / "users"
        for user_dir in user_models.rglob(model_id):
            if (user_dir / "metadata.json").exists():
                return user_dir

        # Search in production
        for prod_dir in self.production_dir.rglob(model_id):
            if (prod_dir / "metadata.json").exists():
                return prod_dir

        raise FileNotFoundError(f"Model directory not found: {model_id}")

    def load_metadata(self, model_dir: Path) -> dict:
        """Load model metadata.json."""
        meta_path = model_dir / "metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"metadata.json not found in {model_dir}")
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)

    def run_backtest(
        self,
        model_id: str,
        dates: list[str],
        horizon: int = 10,
        model_dir: Path | None = None,
        data_dir: Path | str | None = None,
    ) -> dict[str, Any]:
        """
        Run rolling backtest across multiple dates.

        For each date:
        1. Load parquet features
        2. Run model inference → predicted scores
        3. Compare with actual mom_ret_{horizon}d
        4. Compute IC, decile returns

        Returns per-day results + aggregate metrics.
        """
        resolved_dir = model_dir or self.resolve_model_dir(model_id)
        meta = self.load_metadata(resolved_dir)
        feature_cols = meta.get("feature_columns") or meta.get("features", [])
        if not feature_cols:
            raise ValueError("Model metadata has no feature_columns")

        actual_col = f"mom_ret_{horizon}d"

        # Load model once
        cache_key = f"backtest:{model_id}"
        self.model_loader.load_model(model_id, model_dir=resolved_dir, cache_key=cache_key)
        model = self.model_loader.get_model(model_id, cache_key=cache_key)
        if model is None:
            raise ValueError(f"Failed to load model {model_id}")

        results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        self._prev_top_symbols = []  # reset for each backtest run

        for date_str in dates:
            try:
                day_result = self._evaluate_single_date(
                    date_str=date_str,
                    model=model,
                    meta=meta,
                    feature_cols=feature_cols,
                    actual_col=actual_col,
                    data_dir=data_dir,
                )
                if day_result is not None:
                    results.append(day_result)
            except Exception as e:
                logger.warning("回测日期 %s 失败: %s", date_str, e)
                errors.append({"date": date_str, "error": str(e)})

        if not results:
            return {
                "status": "error",
                "model_id": model_id,
                "error": "所有日期回测均失败",
                "errors": errors,
            }

        # Aggregate metrics
        ic_series = [r["ic"] for r in results]
        ic_arr = np.array(ic_series)

        # Random baseline: shuffle predictions, compute IC, repeat 100 times
        rng = np.random.RandomState(42)
        random_ics = []
        for _ in range(100):
            shuffled = ic_arr.copy()
            rng.shuffle(shuffled)
            random_ics.append(float(np.nanmean(shuffled)))
        random_ic_mean = float(np.nanmean(random_ics))
        random_ic_std = float(np.nanstd(random_ics))

        metrics = {
            "ic_mean": float(np.nanmean(ic_arr)),
            "ic_std": float(np.nanstd(ic_arr)),
            "ic_ir": float(np.nanmean(ic_arr) / np.nanstd(ic_arr)) if np.nanstd(ic_arr) > 0 else 0.0,
            "hit_rate": float(np.mean([ic > 0 for ic in ic_series])),
            "ic_positive_rate": float(np.mean([ic > 0 for ic in ic_series])),
            "n_dates": len(results),
            "n_errors": len(errors),
            "random_ic_mean": random_ic_mean,
            "random_ic_std": random_ic_std,
            "ic_vs_random": float(np.nanmean(ic_arr) - random_ic_mean),
            "t_stat": float((np.nanmean(ic_arr) - random_ic_mean) / (np.nanstd(ic_arr) / np.sqrt(len(ic_series)))) if np.nanstd(ic_arr) > 0 and len(ic_series) > 1 else 0.0,
        }

        # Decile aggregation
        decile_keys = list(range(10))
        avg_decile_returns: dict[int, float] = {}
        for d in decile_keys:
            vals = [r["decile_returns"].get(d, 0.0) for r in results if d in r.get("decile_returns", {})]
            avg_decile_returns[d] = float(np.mean(vals)) if vals else 0.0

        metrics["avg_top_decile"] = avg_decile_returns.get(9, 0.0)
        metrics["avg_bottom_decile"] = avg_decile_returns.get(0, 0.0)
        metrics["long_short_return"] = metrics["avg_top_decile"] - metrics["avg_bottom_decile"]

        # Monotonicity: check if decile returns are monotonically increasing
        decile_vals = [avg_decile_returns.get(d, 0.0) for d in range(10)]
        monotone_count = sum(1 for i in range(1, len(decile_vals)) if decile_vals[i] >= decile_vals[i - 1])
        metrics["monotonicity"] = float(monotone_count / (len(decile_vals) - 1)) if len(decile_vals) > 1 else 0.0

        # Rank IC (Spearman of decile vs return)
        try:
            rank_ic = spearmanr(list(range(10)), decile_vals).correlation
            metrics["decile_rank_ic"] = float(rank_ic) if not np.isnan(rank_ic) else 0.0
        except Exception:
            metrics["decile_rank_ic"] = 0.0

        # ── Enhanced metrics ──

        # Turnover
        turnovers = [r.get("top_turnover", 0) for r in results]
        metrics["turnover_mean"] = float(np.mean(turnovers))

        # Long-short series for Sharpe and drawdown
        ls_series = [r.get("top_10pct_return", 0) - r.get("bottom_10pct_return", 0) for r in results]
        ls_arr = np.array(ls_series)
        ls_mean = float(np.mean(ls_arr))
        ls_std = float(np.std(ls_arr)) if len(ls_arr) > 1 else 1.0
        avg_interval = len(dates) / max(len(results), 1)  # approximate trading day interval
        metrics["sharpe_ls"] = float(ls_mean / ls_std * np.sqrt(252 / max(avg_interval, 1))) if ls_std > 0 else 0.0

        # Cumulative series for charts
        metrics["cumulative_ic"] = list(np.cumsum(ic_arr))
        metrics["cumulative_ls"] = list(np.cumsum(ls_arr))

        # Max drawdown of long-short cumulative returns
        cum_ls = np.cumsum(ls_arr)
        metrics["max_drawdown_ls"] = _max_drawdown(cum_ls.tolist())

        # Up/Down capture: IC in up vs down market days
        up_ics = [r["ic"] for r in results if r.get("market_return", 0) > 0.001]
        down_ics = [r["ic"] for r in results if r.get("market_return", 0) < -0.001]
        metrics["up_capture"] = float(np.mean(up_ics)) if up_ics else 0.0
        metrics["down_capture"] = float(np.mean(down_ics)) if down_ics else 0.0

        # Monthly IC breakdown
        metrics["monthly_ic"] = _group_by_month(results)

        output = {
            "status": "success",
            "run_id": uuid.uuid4().hex[:12],
            "model_id": model_id,
            "horizon": horizon,
            "created_at": datetime.now().isoformat(),
            "date_range": [dates[0], dates[-1]] if dates else [],
            "sample_interval": len(dates),
            "metrics": metrics,
            "avg_decile_returns": avg_decile_returns,
            "per_day": results,
            "errors": errors,
        }

        # Auto-save to history
        try:
            self.save_history(model_id, output)
        except Exception as e:
            logger.warning("保存回测历史失败: %s", e)

        return output

    def _evaluate_single_date(
        self,
        date_str: str,
        model: Any,
        meta: dict,
        feature_cols: list[str],
        actual_col: str,
        data_dir: Path | str | None = None,
    ) -> dict[str, Any] | None:
        """Evaluate model on a single date. Returns result dict or None."""
        day_df = load_date_data(date_str, data_dir=data_dir, meta=meta)
        if day_df is None or len(day_df) == 0:
            return None

        # Check if actual return column exists
        if actual_col not in day_df.columns:
            logger.warning("日期 %s 缺少 %s 列", date_str, actual_col)
            return None

        # Prepare features
        X_df, symbols = preprocess(day_df, meta)
        if len(X_df) == 0:
            return None

        # Run prediction
        predictions = self._predict(model, X_df)
        if predictions is None or len(predictions) == 0:
            return None

        # Build results DataFrame
        pred_series = pd.Series(predictions, index=symbols, name="pred")
        actual_series = day_df.set_index("symbol")[actual_col].astype(float)

        joined = pd.DataFrame({"pred": pred_series, "actual": actual_series})
        joined = joined.replace([np.inf, -np.inf], np.nan).dropna()

        # Normalize: if mean |actual| > 1, assume it's percentage (e.g. 10 = 10%)
        if joined["actual"].abs().mean() > 1:
            joined["actual"] = joined["actual"] / 100.0

        # Filter extreme outliers (new stock IPOs, data errors)
        q01 = joined["actual"].quantile(0.01)
        q99 = joined["actual"].quantile(0.99)
        iqr = q99 - q01
        lower = q01 - 3 * iqr
        upper = q99 + 3 * iqr
        before = len(joined)
        joined = joined[(joined["actual"] >= lower) & (joined["actual"] <= upper)]
        if len(joined) < before:
            logger.info("日期 %s 过滤极端值: %d -> %d", date_str, before, len(joined))

        if len(joined) < 20:
            logger.warning("日期 %s 有效样本不足 (%d)", date_str, len(joined))
            return None

        # IC (Spearman rank correlation — robust to outliers)
        ic, _ = spearmanr(joined["pred"], joined["actual"])
        if np.isnan(ic):
            ic = 0.0

        # Decile analysis
        try:
            joined["decile"] = pd.qcut(joined["pred"], 10, labels=False, duplicates="drop")
        except ValueError:
            joined["decile"] = pd.qcut(joined["pred"], 5, labels=False, duplicates="drop")

        decile_returns = joined.groupby("decile")["actual"].mean().to_dict()
        decile_returns = {int(k): float(v) for k, v in decile_returns.items()}

        # Top/Bottom N returns
        n = max(1, len(joined) // 10)
        top_n = joined.nlargest(n, "pred")["actual"].mean()
        bottom_n = joined.nsmallest(n, "pred")["actual"].mean()

        # Market return (equal-weight average)
        market_return = float(joined["actual"].mean())

        # Turnover: % of top decile that changed from previous date
        curr_top = set(joined.nlargest(n, "pred").index)
        if self._prev_top_symbols:
            prev_top = set(self._prev_top_symbols)
            union = prev_top | curr_top
            turnover = len(prev_top.symmetric_difference(curr_top)) / max(len(union), 1)
        else:
            turnover = 0.0
        self._prev_top_symbols = list(curr_top)

        return {
            "date": date_str,
            "ic": float(ic),
            "n_stocks": len(joined),
            "decile_returns": decile_returns,
            "top_10pct_return": float(top_n),
            "bottom_10pct_return": float(bottom_n),
            "pred_mean": float(joined["pred"].mean()),
            "pred_std": float(joined["pred"].std()),
            "actual_mean": float(joined["actual"].mean()),
            "market_return": market_return,
            "top_turnover": float(turnover),
        }

    def run_multi_horizon_backtest(
        self,
        model_id: str,
        dates: list[str],
        horizons: list[int] | None = None,
        model_dir: Path | None = None,
        data_dir: Path | str | None = None,
    ) -> dict[str, Any]:
        """Run backtest across multiple prediction horizons and compare."""
        horizons = horizons or [1, 5, 10, 20]
        horizon_results: dict[str, dict[str, Any]] = {}
        for h in horizons:
            try:
                result = self.run_backtest(
                    model_id=model_id,
                    dates=dates,
                    horizon=h,
                    model_dir=model_dir,
                    data_dir=data_dir,
                )
                horizon_results[f"T+{h}"] = {
                    "ic_mean": result["metrics"]["ic_mean"],
                    "ic_ir": result["metrics"]["ic_ir"],
                    "hit_rate": result["metrics"]["hit_rate"],
                    "long_short_return": result["metrics"]["long_short_return"],
                    "sharpe_ls": result["metrics"].get("sharpe_ls", 0),
                    "max_drawdown_ls": result["metrics"].get("max_drawdown_ls", 0),
                    "turnover_mean": result["metrics"].get("turnover_mean", 0),
                    "n_dates": result["metrics"]["n_dates"],
                }
            except Exception as e:
                logger.warning("Multi-horizon T+%d failed: %s", h, e)
                horizon_results[f"T+{h}"] = {"error": str(e)}

        # Find best horizon by IC_IR
        best = max(
            ((k, v) for k, v in horizon_results.items() if "ic_ir" in v),
            key=lambda x: x[1]["ic_ir"],
            default=(None, None),
        )

        return {
            "status": "success",
            "model_id": model_id,
            "horizons": horizon_results,
            "best_horizon": best[0] if best[0] else "N/A",
        }

    @staticmethod
    def _predict(model: Any, X_df: pd.DataFrame) -> np.ndarray | None:
        """Run model prediction, handling different model types."""
        import lightgbm as lgb

        try:
            # LightGBM Booster
            if hasattr(model, "feature_name"):
                return model.predict(X_df.values.astype(np.float32))

            # XGBoost Booster
            if type(model).__module__.startswith("xgboost"):
                import xgboost as xgb
                dmat = xgb.DMatrix(X_df.values, feature_names=list(X_df.columns))
                return model.predict(dmat)

            # CatBoost
            if hasattr(model, "predict") and type(model).__name__ == "CatBoost":
                return model.predict(X_df.values.astype(np.float32))

            # Ensemble (multiple boosters)
            if hasattr(model, "boosters"):
                preds = [b.predict(X_df.values.astype(np.float32)) for b in model.boosters]
                return np.mean(preds, axis=0)

            # Generic predict
            if hasattr(model, "predict"):
                result = model.predict(X_df)
                if isinstance(result, pd.Series):
                    return result.values
                return np.asarray(result).flatten()

            # Qlib LGBModel wrapper
            inner = getattr(model, "model", None)
            if inner is not None and hasattr(inner, "predict"):
                return inner.predict(X_df.values.astype(np.float32))

            logger.error("Unsupported model type: %s", type(model))
            return None

        except Exception as e:
            logger.error("Prediction failed: %s", e)
            return None

    # ── History persistence ──

    def save_history(self, model_id: str, result: dict[str, Any]) -> None:
        """Save a backtest result to history."""
        history_dir = _HISTORY_DIR / model_id
        history_dir.mkdir(parents=True, exist_ok=True)

        run_id = result.get("run_id", uuid.uuid4().hex[:12])
        ts = result.get("created_at", datetime.now().isoformat())[:19].replace(":", "-")
        filename = f"{ts}_{run_id}.json"
        filepath = history_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info("回测历史已保存: %s", filepath)

        # Cleanup: keep only latest 50 records per model
        self._cleanup_history(model_id, max_records=50)

    def list_history(self, model_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """List backtest history for a model, newest first."""
        history_dir = _HISTORY_DIR / model_id
        if not history_dir.exists():
            return []

        files = sorted(history_dir.glob("*.json"), reverse=True)
        records = []
        for f in files[:limit]:
            try:
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
                # Return summary (without per_day details for list view)
                records.append({
                    "run_id": data.get("run_id", ""),
                    "model_id": data.get("model_id", model_id),
                    "horizon": data.get("horizon", 10),
                    "created_at": data.get("created_at", ""),
                    "date_range": data.get("date_range", []),
                    "metrics": data.get("metrics", {}),
                    "avg_decile_returns": data.get("avg_decile_returns", {}),
                    "n_dates": data.get("metrics", {}).get("n_dates", 0),
                })
            except Exception as e:
                logger.warning("读取回测历史失败 %s: %s", f.name, e)
        return records

    def get_history_detail(self, model_id: str, run_id: str) -> dict[str, Any] | None:
        """Get full detail of a specific backtest run."""
        history_dir = _HISTORY_DIR / model_id
        if not history_dir.exists():
            return None

        for f in history_dir.glob(f"*{run_id}*.json"):
            try:
                with open(f, encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                continue
        return None

    def delete_history(self, model_id: str, run_id: str) -> bool:
        """Delete a specific backtest history record."""
        history_dir = _HISTORY_DIR / model_id
        if not history_dir.exists():
            return False
        for f in history_dir.glob(f"*{run_id}*.json"):
            f.unlink()
            return True
        return False

    @staticmethod
    def _cleanup_history(model_id: str, max_records: int = 50) -> None:
        """Keep only the latest N history records per model."""
        history_dir = _HISTORY_DIR / model_id
        if not history_dir.exists():
            return
        files = sorted(history_dir.glob("*.json"), reverse=True)
        for f in files[max_records:]:
            f.unlink()
