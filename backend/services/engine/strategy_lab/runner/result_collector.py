"""Result data classes + Redis serialization.

The worker pushes a ``RunResult`` JSON blob to ``qm:lab:result:{run_id}``;
the API read endpoint pulls + decodes it.

Keeps the schema in lock-step with §5.3.2 of docs/Strategy_Lab规范.md.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from backend.shared.redis_sentinel_client import get_redis_sentinel_client

from .progress import _TTL_SECONDS, result_key

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    date: str
    symbol: str
    direction: str  # BUY / SELL
    price: float
    qty: int
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    pnl: float | None = None


@dataclass
class EquityPoint:
    date: str
    value: float
    benchmark: float | None = None


@dataclass
class PositionSnapshot:
    date: str
    symbol: str
    qty: int
    cost: float
    market_value: float
    pnl_pct: float


@dataclass
class Metrics:
    cum_return: float = 0.0
    annual_return: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    n_trades: int = 0
    avg_position: float = 0.0


@dataclass
class RunResult:
    """The full payload written to qm:lab:result:{run_id}."""

    run_id: str
    status: str  # success / failed
    metrics: Metrics = field(default_factory=Metrics)
    equity: list[EquityPoint] = field(default_factory=list)
    trades: list[TradeRecord] = field(default_factory=list)
    positions: list[PositionSnapshot] = field(default_factory=list)
    overlays: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    error_traceback: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    script_sha: str = ""
    data_snapshot_at: str | None = None
    elapsed_sec: float = 0.0
    started_at: float = 0.0
    finished_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = asdict(self)
        return _sanitize(d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RunResult":
        m = d.get("metrics") or {}
        eq = [EquityPoint(**p) for p in d.get("equity") or []]
        tr = [TradeRecord(**t) for t in d.get("trades") or []]
        po = [PositionSnapshot(**p) for p in d.get("positions") or []]
        return cls(
            run_id=d["run_id"],
            status=d["status"],
            metrics=Metrics(**m),
            equity=eq,
            trades=tr,
            positions=po,
            overlays=d.get("overlays") or {},
            logs=d.get("logs") or [],
            warnings=d.get("warnings") or [],
            error=d.get("error"),
            error_traceback=d.get("error_traceback"),
            config=d.get("config") or {},
            script_sha=d.get("script_sha", ""),
            data_snapshot_at=d.get("data_snapshot_at"),
            elapsed_sec=d.get("elapsed_sec", 0.0),
            started_at=d.get("started_at", 0.0),
            finished_at=d.get("finished_at", 0.0),
        )


# ---------------------------------------------------------------------------
# Reproducibility hash
# ---------------------------------------------------------------------------
def compute_script_sha(code: str, params: dict[str, Any] | None = None) -> str:
    """Hash code + sorted params — used as ``script_sha`` for repro checks."""
    payload = {
        "code": code,
        "params": _stable_sort(params or {}),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _stable_sort(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _stable_sort(obj[k]) for k in sorted(obj)}
    if isinstance(obj, (list, tuple)):
        return [_stable_sort(v) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# JSON safety — NaN/Inf are not valid JSON; FastAPI will silently break HTTP
# stream when present (see memory feedback_fastapi_nan_serialization).
# ---------------------------------------------------------------------------
def _sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


# ---------------------------------------------------------------------------
# Redis read/write
# ---------------------------------------------------------------------------
def store_result(result: RunResult, redis_client: Any | None = None) -> None:
    redis_client = redis_client or get_redis_sentinel_client()
    try:
        key = result_key(result.run_id)
        # Use the raw .set with bytes — RedisSentinelClient.set takes bytes.
        redis_client.set(key, result.to_json().encode("utf-8"), ex=_TTL_SECONDS)
    except Exception as e:
        logger.warning("store_result failed run_id=%s: %s", result.run_id, e)


def fetch_result(run_id: str, redis_client: Any | None = None) -> RunResult | None:
    redis_client = redis_client or get_redis_sentinel_client()
    try:
        raw = redis_client.get(result_key(run_id))
    except Exception as e:
        logger.warning("fetch_result failed run_id=%s: %s", run_id, e)
        return None
    if not raw:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    try:
        return RunResult.from_dict(json.loads(raw))
    except Exception as e:
        logger.warning("fetch_result decode failed run_id=%s: %s", run_id, e)
        return None
