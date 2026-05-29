from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


class PredictionArtifactError(RuntimeError):
    """Raised when inference output cannot be converted to backtest artifact."""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def build_pred_pkl_from_inference(
    *,
    run_id: str,
    user_id: str,
    tenant_id: str,
    inference_result: dict[str, Any],
    base_dir: Path,
    default_datetime: datetime | None = None,
) -> Path:
    """Convert inference result into qlib-compatible pred.pkl file."""
    predictions = _as_list(inference_result.get("predictions"))
    symbols = _as_list(inference_result.get("symbols"))

    if not predictions:
        raise PredictionArtifactError("inference result missing predictions")

    if symbols and len(symbols) != len(predictions):
        raise PredictionArtifactError(f"symbols/predictions length mismatch: {len(symbols)} != {len(predictions)}")

    if not symbols:
        symbols = [f"UNKNOWN_{idx:04d}" for idx in range(len(predictions))]

    dt = default_datetime or datetime.now()
    dt_index = pd.Timestamp(dt.strftime("%Y-%m-%d"))

    tuples: list[tuple[pd.Timestamp, str]] = []
    scores: list[float] = []
    for symbol, score in zip(symbols, predictions):
        try:
            score_val = float(score)
        except Exception as exc:  # pragma: no cover
            raise PredictionArtifactError(f"invalid prediction value {score!r}: {exc}")
        tuples.append((dt_index, str(symbol)))
        scores.append(score_val)

    df = pd.DataFrame(
        {"score": scores},
        index=pd.MultiIndex.from_tuples(tuples, names=["datetime", "instrument"]),
    )

    output_dir = base_dir / tenant_id / user_id / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "pred.pkl"
    df.to_pickle(output_path)
    return output_path
