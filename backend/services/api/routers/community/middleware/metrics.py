"""Prometheus metrics middleware (P2)."""

from __future__ import annotations

import re
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from prometheus_client import Counter, Histogram  # type: ignore
except Exception:  # pragma: no cover
    Counter = None  # type: ignore
    Histogram = None  # type: ignore


if Counter is not None:
    REQ_COUNT = Counter(
        "community_http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
else:  # pragma: no cover
    REQ_COUNT = None  # type: ignore

if Histogram is not None:
    REQ_LATENCY = Histogram(
        "community_http_request_duration_seconds",
        "HTTP request latency (seconds)",
        ["method", "path"],
        buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )
else:  # pragma: no cover
    REQ_LATENCY = None  # type: ignore


_re_num = re.compile(r"/\d+")


def _normalize_path(raw: str) -> str:
    # reduce label cardinality: replace "/123" with "/:id"
    return _re_num.sub("/:id", raw)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if REQ_COUNT is None or REQ_LATENCY is None:
            return await call_next(request)

        start = time.perf_counter()
        resp = await call_next(request)
        elapsed = time.perf_counter() - start

        # Prefer route template if available, fallback to request path.
        route = request.scope.get("route")
        route_path = getattr(route, "path", None) or request.url.path
        path = _normalize_path(str(route_path))

        REQ_COUNT.labels(request.method, path, str(resp.status_code)).inc()
        REQ_LATENCY.labels(request.method, path).observe(elapsed)
        return resp
