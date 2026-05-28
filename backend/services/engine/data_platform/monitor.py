"""
数据源健康监控。

Redis Key 设计：
    quantmind:datasource:health:{source}:{field}

Hash 字段：
    last_success_at          ISO8601
    last_error_at            ISO8601
    last_error_msg           最近一次错误信息（截断 256 字符）
    rows_today               今日累计写入行数
    rows_yesterday           昨日累计写入行数
    avg_latency_ms           滑动平均（指数衰减 alpha=0.2）
    p95_latency_ms           最近 100 次请求的近似 p95
    error_rate_1h            最近 1 小时错误率
    error_rate_24h           最近 24 小时错误率
    fallback_triggered_count 今日切到备用源次数
    consensus_deviation_avg  共识投票偏离度（fraction）

为避免 Redis 强依赖：构造函数允许 redis_client=None，此时退化为内存字典，
便于单测与本地调试。
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

HEALTH_KEY_PREFIX = "quantmind:datasource:health"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _InMemoryBackend:
    """Redis 不可用时的退化实现。线程安全。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._h: dict[str, dict[str, str]] = defaultdict(dict)

    def hset(self, key: str, mapping: dict[str, Any]) -> None:
        with self._lock:
            for k, v in mapping.items():
                self._h[key][k] = str(v)

    def hgetall(self, key: str) -> dict[str, str]:
        with self._lock:
            return dict(self._h.get(key, {}))

    def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        with self._lock:
            cur = int(self._h[key].get(field, "0"))
            cur += amount
            self._h[key][field] = str(cur)
            return cur


class HealthMonitor:
    """记录适配器调用结果，写入 Redis（或内存）。"""

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        *,
        latency_window: int = 100,
    ) -> None:
        self.redis = redis_client or _InMemoryBackend()
        self.latency_window = latency_window
        # 进程内滑窗：(source, field) -> deque[latency_ms]
        self._latencies: dict[tuple[str, str], deque[float]] = defaultdict(
            lambda: deque(maxlen=latency_window)
        )
        # 进程内事件：(source, field) -> deque[(ts, is_error)]
        self._events: dict[tuple[str, str], deque[tuple[float, bool]]] = defaultdict(
            lambda: deque(maxlen=1024)
        )
        self._lock = threading.RLock()

    # ---- key helpers ----
    @staticmethod
    def _key(source: str, field: str) -> str:
        return f"{HEALTH_KEY_PREFIX}:{source}:{field}"

    # ---- mutation API ----
    def record_success(
        self,
        source: str,
        field: str,
        *,
        rows: int = 0,
        latency_ms: float = 0.0,
    ) -> None:
        self._record_event(source, field, is_error=False, latency_ms=latency_ms)
        key = self._key(source, field)
        mapping = {
            "last_success_at": _iso_now(),
            "avg_latency_ms": f"{self._avg_latency(source, field):.2f}",
            "p95_latency_ms": f"{self._p95_latency(source, field):.2f}",
            "error_rate_1h": f"{self._error_rate(source, field, window_sec=3600):.4f}",
            "error_rate_24h": f"{self._error_rate(source, field, window_sec=86400):.4f}",
        }
        self._safe_hset(key, mapping)
        if rows > 0:
            self._safe_hincrby(key, "rows_today", rows)

    def record_error(
        self,
        source: str,
        field: str,
        *,
        error: str,
        latency_ms: float = 0.0,
    ) -> None:
        self._record_event(source, field, is_error=True, latency_ms=latency_ms)
        key = self._key(source, field)
        mapping = {
            "last_error_at": _iso_now(),
            "last_error_msg": str(error)[:256],
            "avg_latency_ms": f"{self._avg_latency(source, field):.2f}",
            "p95_latency_ms": f"{self._p95_latency(source, field):.2f}",
            "error_rate_1h": f"{self._error_rate(source, field, window_sec=3600):.4f}",
            "error_rate_24h": f"{self._error_rate(source, field, window_sec=86400):.4f}",
        }
        self._safe_hset(key, mapping)

    def record_fallback(self, source: str, field: str) -> None:
        self._safe_hincrby(self._key(source, field), "fallback_triggered_count", 1)

    def record_consensus_deviation(
        self,
        source: str,
        field: str,
        *,
        deviation: float,
    ) -> None:
        """记录共识投票时该源的偏离度（0~1）。简单 EMA 平均。"""
        key = self._key(source, field)
        cur = self.get_health(source, field).get("consensus_deviation_avg")
        try:
            prev = float(cur) if cur is not None else None
        except ValueError:
            prev = None
        new = deviation if prev is None else (prev * 0.8 + deviation * 0.2)
        self._safe_hset(key, {"consensus_deviation_avg": f"{new:.4f}"})

    # ---- query API ----
    def get_health(self, source: str, field: str) -> dict[str, Any]:
        return self._safe_hgetall(self._key(source, field))

    # ---- internal ----
    def _record_event(
        self,
        source: str,
        field: str,
        *,
        is_error: bool,
        latency_ms: float,
    ) -> None:
        with self._lock:
            self._latencies[(source, field)].append(float(latency_ms))
            self._events[(source, field)].append((time.time(), is_error))

    def _avg_latency(self, source: str, field: str) -> float:
        d = self._latencies.get((source, field))
        if not d:
            return 0.0
        return sum(d) / len(d)

    def _p95_latency(self, source: str, field: str) -> float:
        d = self._latencies.get((source, field))
        if not d:
            return 0.0
        s = sorted(d)
        idx = max(0, int(len(s) * 0.95) - 1)
        return s[idx]

    def _error_rate(self, source: str, field: str, *, window_sec: int) -> float:
        d = self._events.get((source, field))
        if not d:
            return 0.0
        cutoff = time.time() - window_sec
        recent = [e for e in d if e[0] >= cutoff]
        if not recent:
            return 0.0
        return sum(1 for _, err in recent if err) / len(recent)

    # ---- redis-safe wrappers ----
    def _safe_hset(self, key: str, mapping: dict[str, Any]) -> None:
        try:
            self.redis.hset(key, mapping=mapping)
        except TypeError:
            # 兼容 _InMemoryBackend 签名
            self.redis.hset(key, mapping)
        except Exception as exc:  # noqa: BLE001
            logger.warning("HealthMonitor hset failed for %s: %s", key, exc)

    def _safe_hincrby(self, key: str, field: str, amount: int = 1) -> None:
        try:
            self.redis.hincrby(key, field, amount)
        except Exception as exc:  # noqa: BLE001
            logger.warning("HealthMonitor hincrby failed for %s.%s: %s", key, field, exc)

    def _safe_hgetall(self, key: str) -> dict[str, Any]:
        try:
            raw = self.redis.hgetall(key) or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("HealthMonitor hgetall failed for %s: %s", key, exc)
            return {}
        out: dict[str, Any] = {}
        for k, v in raw.items():
            if isinstance(k, bytes):
                k = k.decode("utf-8", errors="ignore")
            if isinstance(v, bytes):
                v = v.decode("utf-8", errors="ignore")
            out[k] = v
        return out


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------
_monitor: Optional[HealthMonitor] = None
_monitor_lock = threading.Lock()


def get_monitor(redis_client: Optional[Any] = None) -> HealthMonitor:
    global _monitor
    if _monitor is None:
        with _monitor_lock:
            if _monitor is None:
                _monitor = HealthMonitor(redis_client=redis_client)
    return _monitor
