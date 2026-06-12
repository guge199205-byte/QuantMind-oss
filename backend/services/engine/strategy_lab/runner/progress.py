"""Progress publishing — runner-side writer, API-side reader.

Each run gets two Redis keys:
- ``qm:lab:progress:{run_id}``   — list of JSON events (append-only)
- ``qm:lab:run:{run_id}``        — hash of run metadata + final result blob

The worker subprocess pushes events; the SSE endpoint reads them. We keep
a TTL on both keys so a forgotten run is reaped after 1 hour.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from backend.shared.redis_sentinel_client import get_redis_sentinel_client

logger = logging.getLogger(__name__)

# Spec §5.4 — Redis keys
_KEY_EVENTS = "qm:lab:progress:{run_id}"
_KEY_META = "qm:lab:run:{run_id}"
_KEY_RESULT = "qm:lab:result:{run_id}"
_KEY_SCRIPT = "qm:lab:script:{run_id}"
_TTL_SECONDS = 3600  # 1 hour


class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class Phase(str, Enum):
    queued = "queued"
    boot = "boot"
    ast_check = "ast_check"
    setup = "setup"
    load_data = "load_data"
    backtest = "backtest"
    aggregate = "aggregate"
    done = "done"


@dataclass
class ProgressEvent:
    """One progress update written to the Redis event list."""

    run_id: str
    phase: Phase
    pct: float = 0.0
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    ts: float = 0.0

    def __post_init__(self) -> None:
        if self.ts == 0.0:
            self.ts = time.time()
        self.pct = max(0.0, min(100.0, float(self.pct)))

    def to_json(self) -> str:
        d = asdict(self)
        d["phase"] = self.phase.value
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str | bytes) -> "ProgressEvent":
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        d = json.loads(raw)
        return cls(
            run_id=d["run_id"],
            phase=Phase(d["phase"]),
            pct=d.get("pct", 0.0),
            message=d.get("message", ""),
            detail=d.get("detail") or {},
            ts=d.get("ts", time.time()),
        )


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------
def events_key(run_id: str) -> str:
    return _KEY_EVENTS.format(run_id=run_id)


def meta_key(run_id: str) -> str:
    return _KEY_META.format(run_id=run_id)


def result_key(run_id: str) -> str:
    return _KEY_RESULT.format(run_id=run_id)


def script_key(run_id: str) -> str:
    return _KEY_SCRIPT.format(run_id=run_id)


# ---------------------------------------------------------------------------
# Publisher (writer side — used by worker subprocess and router)
# ---------------------------------------------------------------------------
class ProgressPublisher:
    """Push events into Redis. Tolerant of Redis hiccups."""

    def __init__(self, run_id: str, redis_client: Any | None = None) -> None:
        self.run_id = run_id
        self._redis = redis_client or get_redis_sentinel_client()

    def publish(
        self,
        phase: Phase,
        pct: float = 0.0,
        message: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        evt = ProgressEvent(
            run_id=self.run_id, phase=phase, pct=pct, message=message,
            detail=detail or {},
        )
        try:
            self._redis.rpush(events_key(self.run_id), evt.to_json())
            self._redis.expire(events_key(self.run_id), _TTL_SECONDS)
        except Exception as e:  # never crash the runner because of Redis
            logger.warning("ProgressPublisher.publish failed run_id=%s: %s", self.run_id, e)

    def set_status(self, status: RunStatus, **fields: Any) -> None:
        try:
            payload: dict[str, Any] = {"status": status.value, "updated_at": str(time.time())}
            for k, v in fields.items():
                payload[k] = json.dumps(v) if not isinstance(v, (str, int, float, bool)) else str(v)
            self._redis.hset(meta_key(self.run_id), mapping=payload)
            self._redis.expire(meta_key(self.run_id), _TTL_SECONDS)
        except Exception as e:
            logger.warning("ProgressPublisher.set_status failed run_id=%s: %s", self.run_id, e)


# ---------------------------------------------------------------------------
# Reader (API side — used by SSE endpoint)
# ---------------------------------------------------------------------------
class ProgressReader:
    def __init__(self, run_id: str, redis_client: Any | None = None) -> None:
        self.run_id = run_id
        self._redis = redis_client or get_redis_sentinel_client()

    def fetch_events(self, start: int = 0, end: int = -1) -> list[ProgressEvent]:
        raw = self._redis.lrange(events_key(self.run_id), start, end) or []
        events: list[ProgressEvent] = []
        for r in raw:
            try:
                events.append(ProgressEvent.from_json(r))
            except Exception:
                continue
        return events

    def fetch_meta(self) -> dict[str, Any]:
        meta = self._redis.hgetall(meta_key(self.run_id)) or {}
        out: dict[str, Any] = {}
        for k, v in meta.items():
            key = k.decode() if isinstance(k, (bytes, bytearray)) else k
            val = v.decode() if isinstance(v, (bytes, bytearray)) else v
            out[key] = val
        return out
