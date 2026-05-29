"""
Prometheus metrics instrumentation for FastAPI services
"""

import time
from collections.abc import Callable

from fastapi import FastAPI
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def create_metric(metric_class, name, documentation, labelnames=(), **kwargs):
    """Safely create a metric or return existing one if name conflicts"""
    if name in REGISTRY._names_to_collectors:
        return REGISTRY._names_to_collectors[name]
    return metric_class(name, documentation, labelnames=labelnames, **kwargs)


# 创建指标
REQUEST_COUNT = create_metric(
    Counter,
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_DURATION = create_metric(
    Histogram,
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

REQUEST_IN_PROGRESS = create_metric(
    Gauge,
    "http_requests_in_progress",
    "HTTP requests in progress",
    ["method", "endpoint"],
)

DB_POOL_SIZE = create_metric(Gauge, "db_pool_size", "Database connection pool size", ["database"])

DB_POOL_ACTIVE = create_metric(Gauge, "db_pool_active_connections", "Active database connections", ["database"])


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Prometheus metrics middleware"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 忽略metrics端点本身
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        endpoint = request.url.path

        # 请求开始
        REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()
        start_time = time.time()

        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            status = 500
            raise
        finally:
            # 请求结束
            duration = time.time() - start_time
            REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

        return response


def setup_metrics(app: FastAPI):
    """Setup Prometheus metrics for FastAPI app"""

    # 添加metrics中间件
    app.add_middleware(PrometheusMiddleware)

    # 添加metrics端点
    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def update_db_pool_metrics(database_name: str, pool_size: int, active_connections: int):
    """Update database pool metrics"""
    DB_POOL_SIZE.labels(database=database_name).set(pool_size)
    DB_POOL_ACTIVE.labels(database=database_name).set(active_connections)


# ============================================================================
# ServiceRouter 监控指标
# ============================================================================

# 路由决策指标
# 路由决策指标
ROUTER_ROUTE_TOTAL = create_metric(
    Counter,
    "router_route_total",
    "Total number of routing decisions",
    ["task_type", "provider"],
)

ROUTER_ROUTE_DURATION = create_metric(
    Histogram,
    "router_route_duration_seconds",
    "Time spent on routing decisions in seconds",
    ["task_type", "provider"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# 服务健康指标
ROUTER_CIRCUIT_BREAKER_STATE = create_metric(
    Gauge,
    "router_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open)",
    ["provider"],
)

ROUTER_SERVICE_AVAILABLE = create_metric(
    Gauge,
    "router_service_available",
    "Service availability (0=unavailable, 1=available)",
    ["provider"],
)

# 服务调用指标
ROUTER_CALL_TOTAL = create_metric(
    Counter,
    "router_call_total",
    "Total number of service calls",
    ["provider", "status"],
)

ROUTER_CALL_DURATION = create_metric(
    Histogram,
    "router_call_duration_seconds",
    "Service call duration in seconds",
    ["provider"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

ROUTER_FAILURE_RATE = create_metric(Gauge, "router_failure_rate", "Service failure rate (0.0-1.0)", ["provider"])

# 活跃请求指标
ROUTER_ACTIVE_REQUESTS = create_metric(
    Gauge, "router_active_requests", "Number of currently active requests", ["provider"]
)


def update_router_service_health(provider: str, available: bool, circuit_open: bool):
    """更新路由器服务健康指标.

    Args:
        provider: 服务提供商名称
        available: 服务是否可用
        circuit_open: 熔断器是否开启
    """
    ROUTER_SERVICE_AVAILABLE.labels(provider=provider).set(1 if available else 0)
    ROUTER_CIRCUIT_BREAKER_STATE.labels(provider=provider).set(1 if circuit_open else 0)


def update_router_failure_rate(provider: str, failure_rate: float):
    """更新路由器服务失败率.

    Args:
        provider: 服务提供商名称
        failure_rate: 失败率 (0.0-1.0)
    """
    ROUTER_FAILURE_RATE.labels(provider=provider).set(failure_rate)
