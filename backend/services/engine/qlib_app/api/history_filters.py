"""Qlib 历史过滤工具"""

from datetime import datetime
from typing import Any

from sqlalchemy import text

from backend.shared.database_manager_v2 import get_session
from backend.shared.utils import normalize_user_id


async def _filter_optimization_sub_backtests(
    results: list[Any],
    *,
    user_id: str,
    tenant_id: str,
) -> list[Any]:
    candidate_ids = []
    for item in results:
        if isinstance(item, dict):
            backtest_id = item.get("backtest_id")
        else:
            backtest_id = getattr(item, "backtest_id", None)
        if backtest_id:
            candidate_ids.append(str(backtest_id))

    if not candidate_ids:
        return results

    try:
        async with get_session(read_only=True) as session:
            rows = await session.execute(
                text("""
                    SELECT DISTINCT elem->'metrics'->>'backtest_id' AS backtest_id
                    FROM qlib_optimization_runs r
                    CROSS JOIN LATERAL jsonb_array_elements(COALESCE(r.all_results_json, '[]'::jsonb)) elem
                    WHERE r.user_id = :user_id
                      AND r.tenant_id = :tenant_id
                      AND elem ? 'metrics'
                      AND (elem->'metrics'->>'backtest_id') = ANY(:candidate_ids)
                    """),
                {
                    "user_id": normalize_user_id(user_id),
                    "tenant_id": tenant_id,
                    "candidate_ids": candidate_ids,
                },
            )
            excluded_ids = {str(row["backtest_id"]) for row in rows.mappings().all() if row.get("backtest_id")}
    except Exception:
        return results

    if not excluded_ids:
        return results

    filtered = []
    for item in results:
        if isinstance(item, dict):
            backtest_id = item.get("backtest_id")
        else:
            backtest_id = getattr(item, "backtest_id", None)
        if str(backtest_id or "") in excluded_ids:
            continue
        filtered.append(item)
    return filtered


def _filter_legacy_optimization_clusters(results: list[Any]) -> list[Any]:
    def _field(item: Any, key: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    def _cfg(item: Any) -> dict:
        config = _field(item, "config", {}) or {}
        return config if isinstance(config, dict) else {}

    clusters: dict[tuple[str, str, str, str, str], list[Any]] = {}
    for item in results:
        config = _cfg(item)
        params = config.get("qlib_strategy_params") or {}
        if not isinstance(params, dict):
            continue
        if config.get("qlib_strategy_type") != "TopkDropout":
            continue
        if "topk" not in params or "n_drop" not in params:
            continue
        created_at = _field(item, "created_at")
        if not created_at:
            continue
        created_raw = str(created_at)
        try:
            dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            window_start = dt.replace(
                minute=(dt.minute // 5) * 5,
                second=0,
                microsecond=0,
            )
            time_bucket = window_start.strftime("%Y-%m-%d %H:%M")
        except Exception:
            time_bucket = created_raw[:16]
        key = (
            str(_field(item, "user_id", "") or ""),
            str(_field(item, "tenant_id", "default") or "default"),
            str(config.get("start_date") or ""),
            str(config.get("end_date") or ""),
            time_bucket,
        )
        clusters.setdefault(key, []).append(item)

    drop_ids: set[str] = set()
    for items in clusters.values():
        if len(items) < 3:
            continue
        combos = set()
        for item in items:
            config = _cfg(item)
            params = config.get("qlib_strategy_params") or {}
            if isinstance(params, dict):
                combos.add((str(params.get("topk")), str(params.get("n_drop"))))
        if len(combos) >= 3:
            for item in items:
                backtest_id = _field(item, "backtest_id")
                if backtest_id:
                    drop_ids.add(str(backtest_id))

    if not drop_ids:
        return results

    filtered = []
    for item in results:
        backtest_id = _field(item, "backtest_id")
        if str(backtest_id or "") in drop_ids:
            continue
        filtered.append(item)
    return filtered
