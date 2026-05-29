import os
from typing import Optional

from fastapi import FastAPI

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except Exception:  # pragma: no cover
    _OTEL_AVAILABLE = False


def init_tracing(app: FastAPI, sqlalchemy_engine: object | None = None) -> bool:
    """Initialize OpenTelemetry tracing if dependencies & env enabled.

    Returns True if tracing initialized, else False.
    Control via env:
      ENABLE_TRACING=true
      OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
      OTEL_SERVICE_NAME=quantmind-api (fallback SERVICE_NAME)
    """
    if not _OTEL_AVAILABLE:
        return False
    if os.getenv("ENABLE_TRACING", "false").lower() not in (
        "1",
        "true",
        "yes",
    ):  # feature flag
        return False

    service_name = os.getenv("OTEL_SERVICE_NAME") or os.getenv("SERVICE_NAME", "quantmind-api")
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": os.getenv("SERVICE_VERSION", "unknown"),
            "deployment.environment": os.getenv("DEPLOY_ENV", "dev"),
        }
    )

    provider = TracerProvider(resource=resource)
    span_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
    provider.add_span_processor(span_processor)
    trace.set_tracer_provider(provider)

    # Instrumentations
    FastAPIInstrumentor.instrument_app(app)
    RequestsInstrumentor().instrument()
    RedisInstrumentor().instrument()
    if sqlalchemy_engine is not None:
        try:
            SQLAlchemyInstrumentor().instrument(engine=sqlalchemy_engine)  # type: ignore
        except Exception:  # pragma: no cover
            pass
    return True


__all__ = ["init_tracing"]
