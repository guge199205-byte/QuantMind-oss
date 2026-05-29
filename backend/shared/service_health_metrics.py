"""Service health metrics helpers for FastAPI services."""

from fastapi import Response

try:
    from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Gauge, generate_latest

    def _create_gauge(name: str, documentation: str, labelnames=()):
        collector = REGISTRY._names_to_collectors.get(name)  # type: ignore[attr-defined]
        if collector is not None:
            return collector
        return Gauge(name, documentation, labelnames=labelnames)

    SERVICE_HEALTH_STATUS = _create_gauge(
        "quantmind_service_health_status",
        "Service health status (1 healthy, 0 unhealthy)",
        ["service"],
    )
    SERVICE_DEGRADED = _create_gauge(
        "quantmind_service_degraded",
        "Service degraded status (1 degraded, 0 healthy)",
        ["service"],
    )
except Exception:  # pragma: no cover - metrics is optional
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    SERVICE_HEALTH_STATUS = None
    SERVICE_DEGRADED = None

    def generate_latest() -> bytes:
        return b"# metrics unavailable\n"


def set_service_health(service_name: str, healthy: bool) -> None:
    """Update service-level health gauges."""
    if SERVICE_HEALTH_STATUS is not None:
        SERVICE_HEALTH_STATUS.labels(service=service_name).set(1 if healthy else 0)
    if SERVICE_DEGRADED is not None:
        SERVICE_DEGRADED.labels(service=service_name).set(0 if healthy else 1)


def build_metrics_response() -> Response:
    """Build a Prometheus text response."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
