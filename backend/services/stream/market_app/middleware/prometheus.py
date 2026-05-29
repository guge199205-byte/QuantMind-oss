"""Prometheus metrics middleware"""

import time

from fastapi import Request
from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

# Metrics
request_count = Counter(
    "market_data_requests_total",
    "Total request count",
    ["method", "endpoint", "status"],
)

request_duration = Histogram(
    "market_data_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
)

active_connections = Gauge("market_data_active_connections", "Number of active connections")

quote_fetch_count = Counter("market_data_quote_fetch_total", "Total quote fetch count", ["source", "status"])

kline_fetch_count = Counter("market_data_kline_fetch_total", "Total kline fetch count", ["interval", "status"])


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Prometheus metrics collector"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Record metrics
        duration = time.time() - start_time

        request_count.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
        ).inc()

        request_duration.labels(method=request.method, endpoint=request.url.path).observe(duration)

        return response
