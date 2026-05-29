"""
Guards for deciding whether a real-account snapshot is usable for persistence/display.
"""

from __future__ import annotations

from typing import Any, Optional

_EPSILON = 1e-8


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        parsed = float(value)
        return parsed if parsed == parsed else default
    except Exception:
        return default


def extract_positions_count(payload_json: dict[str, Any] | None = None) -> int:
    if not isinstance(payload_json, dict):
        return 0
    positions = payload_json.get("positions")
    if isinstance(positions, list):
        return len(positions)
    if isinstance(positions, dict):
        return len(positions)
    return 0


def is_effectively_empty_snapshot(
    *,
    total_asset: Any,
    cash: Any,
    market_value: Any,
    payload_json: dict[str, Any] | None = None,
) -> bool:
    """
    Treat all-zero asset snapshots without positions as unusable.

    This typically happens when the bridge loses the QMT asset object during
    shutdown/reconnect, but the report still reaches the server.
    """
    total_asset_num = _to_float(total_asset, 0.0)
    cash_num = _to_float(cash, 0.0)
    market_value_num = _to_float(market_value, 0.0)
    positions_count = extract_positions_count(payload_json)
    return (
        total_asset_num <= _EPSILON
        and cash_num <= _EPSILON
        and market_value_num <= _EPSILON
        and positions_count <= 0
    )


def is_inconsistent_zero_total_snapshot(
    *,
    total_asset: Any,
    cash: Any,
    market_value: Any,
    payload_json: dict[str, Any] | None = None,
) -> bool:
    """
    Detect snapshots whose total_asset collapses to zero while cash / market_value / positions still exist.

    This shape is almost always a partial payload or bridge desync, and must not be treated
    as a usable real-account snapshot.
    """
    total_asset_num = _to_float(total_asset, 0.0)
    cash_num = _to_float(cash, 0.0)
    market_value_num = _to_float(market_value, 0.0)
    positions_count = extract_positions_count(payload_json)
    return (
        total_asset_num <= _EPSILON
        and (
            cash_num > _EPSILON
            or market_value_num > _EPSILON
            or positions_count > 0
        )
    )


def is_suspicious_asset_jump(
    *,
    total_asset: Any,
    cash: Any,
    market_value: Any,
    prev_total_asset: Any,
    prev_cash: Any,
    prev_market_value: Any,
    payload_json: dict[str, Any] | None = None,
) -> bool:
    """
    Detect severe asset jumps that are likely caused by partial bridge payload loss.
    """
    total_asset_num = _to_float(total_asset, 0.0)
    cash_num = _to_float(cash, 0.0)
    market_value_num = _to_float(market_value, 0.0)
    prev_total_asset_num = _to_float(prev_total_asset, 0.0)
    prev_cash_num = _to_float(prev_cash, 0.0)
    prev_market_value_num = _to_float(prev_market_value, 0.0)
    positions_count = extract_positions_count(payload_json)

    if prev_total_asset_num <= _EPSILON or total_asset_num <= _EPSILON:
        return False

    total_asset_drop_ratio = total_asset_num / prev_total_asset_num
    cash_drop_ratio = cash_num / prev_cash_num if prev_cash_num > _EPSILON else 1.0
    market_value_drop_ratio = (
        market_value_num / prev_market_value_num if prev_market_value_num > _EPSILON else 1.0
    )

    severe_balance_sheet_collapse = (
        total_asset_drop_ratio < 0.2
        and cash_drop_ratio < 0.2
        and market_value_drop_ratio < 0.2
    )
    positions_present_but_market_missing = (
        positions_count > 0
        and prev_market_value_num > max(prev_total_asset_num * 0.2, 1.0)
        and market_value_num <= _EPSILON
    )
    return severe_balance_sheet_collapse or positions_present_but_market_missing
