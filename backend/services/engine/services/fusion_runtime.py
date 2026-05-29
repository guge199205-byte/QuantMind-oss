from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from backend.services.engine.services.fusion_config import FusionRulesConfig


@dataclass
class FusionExecutionResult:
    pred_path: Path
    report: dict[str, Any]


def _load_pred_scores(pred_path: Path) -> tuple[pd.Timestamp, pd.DataFrame]:
    pred = pd.read_pickle(pred_path)
    if isinstance(pred, pd.Series):
        pred = pred.to_frame("score")
    if "score" not in pred.columns and pred.shape[1] >= 1:
        pred = pred.rename(columns={pred.columns[-1]: "score"})
    if "score" not in pred.columns:
        raise ValueError("pred file does not contain score column")
    if not isinstance(pred.index, pd.MultiIndex):
        raise ValueError("pred file index must be MultiIndex(datetime, instrument)")
    if "datetime" not in pred.index.names or "instrument" not in pred.index.names:
        raise ValueError("pred file index must include datetime/instrument")

    pred = pred.sort_index()
    latest_dt = pred.index.get_level_values("datetime").max()
    daily = pred.xs(latest_dt, level="datetime")[["score"]].copy()
    daily.index = daily.index.astype(str)
    daily = daily.rename(columns={"score": "lgbm_score"})
    return pd.Timestamp(latest_dt), daily


def _build_tft_frame(tft_result: dict[str, Any] | None) -> pd.DataFrame | None:
    if not tft_result:
        return None
    predictions = tft_result.get("predictions")
    symbols = tft_result.get("symbols")
    if not isinstance(predictions, list) or not isinstance(symbols, list):
        return None
    if len(predictions) == 0 or len(symbols) != len(predictions):
        return None

    confidences = tft_result.get("confidences")
    if not isinstance(confidences, list) or len(confidences) != len(predictions):
        confidences = [None] * len(predictions)

    tft_df = pd.DataFrame(
        {
            "instrument": [str(s) for s in symbols],
            "tft_score": [float(v) for v in predictions],
            "tft_confidence": [float(v) if v is not None else None for v in confidences],
        }
    ).drop_duplicates(subset=["instrument"], keep="last")
    return tft_df.set_index("instrument")


def _rank_score(series: pd.Series) -> pd.Series:
    return series.rank(method="average", ascending=False, pct=True)


def apply_fusion_rules(
    *,
    run_id: str,
    user_id: str,
    tenant_id: str,
    base_pred_path: Path,
    base_dir: Path,
    fusion_rules: FusionRulesConfig,
    tft_result: dict[str, Any] | None = None,
    risk_features: dict[str, dict[str, Any]] | None = None,
) -> FusionExecutionResult:
    dt, pred_df = _load_pred_scores(base_pred_path)
    report: dict[str, Any] = {
        "enabled": bool(fusion_rules.enabled),
        "base_pred_path": str(base_pred_path.resolve()),
        "base_count": int(len(pred_df)),
        "used_tft": False,
        "fallback_reason": None,
    }
    if not fusion_rules.enabled:
        return FusionExecutionResult(pred_path=base_pred_path, report=report)

    layer1 = fusion_rules.layer1_lgbm
    layer2 = fusion_rules.layer2_tft
    layer3 = fusion_rules.layer3_risk_gate
    merge_cfg = fusion_rules.merge

    working = pred_df.sort_values("lgbm_score", ascending=False)
    if layer1.enabled:
        working = working.head(layer1.select_top_n)
    report["after_layer1_count"] = int(len(working))

    candidate = working.copy()
    if layer2.enabled:
        candidate = candidate.head(layer2.prefilter_top_n)
        tft_df = _build_tft_frame(tft_result)
        if tft_df is not None and not tft_df.empty:
            candidate = candidate.join(tft_df, how="left")
            report["used_tft"] = True
            report["tft_coverage"] = int(candidate["tft_score"].notna().sum())
        else:
            candidate["tft_score"] = None
            candidate["tft_confidence"] = None
            report["fallback_reason"] = "tft_result_unavailable"

        lgbm_rank = _rank_score(candidate["lgbm_score"])
        tft_rank_raw = _rank_score(candidate["tft_score"].fillna(candidate["lgbm_score"]))
        if merge_cfg.fallback == "lgbm_only":
            tft_rank = tft_rank_raw.fillna(lgbm_rank)
        else:
            tft_rank = tft_rank_raw.fillna(0.0)
        merged = merge_cfg.lgbm_weight * lgbm_rank + merge_cfg.tft_weight * tft_rank

        confidence = candidate.get("tft_confidence")
        if confidence is None:
            confidence = pd.Series(1.0, index=candidate.index)
        confidence = confidence.fillna(1.0 if merge_cfg.fallback == "lgbm_only" else 0.0)
        if layer2.gate_mode == "hard":
            candidate = candidate[confidence >= layer2.min_confidence]
            merged = merged.loc[candidate.index]
        else:
            merged = merged * confidence.clip(lower=0.0, upper=1.0)

        candidate["fusion_score"] = merged
        candidate = candidate.sort_values("fusion_score", ascending=False).head(layer2.final_top_n)
    else:
        candidate["fusion_score"] = _rank_score(candidate["lgbm_score"])
        candidate = candidate.head(layer1.output_top_n)
    report["after_layer2_count"] = int(len(candidate))

    if layer3.enabled and risk_features:
        risk_df = pd.DataFrame.from_dict(risk_features, orient="index")
        risk_df.index = risk_df.index.astype(str)
        candidate = candidate.join(risk_df, how="left")

        if layer3.liquidity_gate.enabled and "avg_turnover_20d" in candidate.columns:
            candidate = candidate[
                candidate["avg_turnover_20d"].fillna(0.0) >= layer3.liquidity_gate.min_avg_turnover_20d
            ]
        if layer3.volatility_gate.enabled and "volatility_20d" in candidate.columns:
            candidate = candidate[
                candidate["volatility_20d"].fillna(float("inf")) <= layer3.volatility_gate.max_volatility_20d
            ]

        if "industry" in candidate.columns:
            sorted_df = candidate.sort_values("fusion_score", ascending=False)
            max_industry_count = max(1, int(layer2.final_top_n * layer3.max_industry_weight))
            industry_counter: dict[str, int] = {}
            kept = []
            for inst, row in sorted_df.iterrows():
                industry = str(row.get("industry") or "unknown")
                if industry_counter.get(industry, 0) >= max_industry_count:
                    continue
                industry_counter[industry] = industry_counter.get(industry, 0) + 1
                kept.append(inst)
            candidate = sorted_df.loc[kept]
    report["after_layer3_count"] = int(len(candidate))

    final_n = layer2.final_top_n if layer2.enabled else layer1.output_top_n
    candidate = candidate.sort_values("fusion_score", ascending=False).head(final_n)
    if candidate.empty:
        raise ValueError("fusion result is empty after filters")

    out_df = pd.DataFrame(
        {"score": candidate["fusion_score"].astype(float).tolist()},
        index=pd.MultiIndex.from_tuples(
            [(dt, inst) for inst in candidate.index.tolist()],
            names=["datetime", "instrument"],
        ),
    )
    output_dir = base_dir / tenant_id / user_id / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "fused_pred.pkl"
    out_df.to_pickle(output_path)

    report.update(
        {
            "final_count": int(len(candidate)),
            "selected_instruments": candidate.index.tolist(),
            "selected_scores": [float(v) for v in candidate["fusion_score"].tolist()],
            "fused_pred_path": str(output_path.resolve()),
            "generated_at": datetime.now().isoformat(),
        }
    )
    return FusionExecutionResult(pred_path=output_path, report=report)
