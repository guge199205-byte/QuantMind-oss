"""
OpenTelemetry链路追踪配置模块

提供统一的分布式追踪配置，支持OTLP导出到Jaeger
"""

import logging
import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

logger = logging.getLogger(__name__)


def setup_tracing(
    service_name: str,
    otlp_endpoint: str = "http://localhost:4317",
    sampling_rate: float = 0.1,
    console_export: bool = False,
) -> trace.Tracer:
    """
    配置OpenTelemetry追踪.

    Args:
        service_name: 服务名称
        otlp_endpoint: OTLP gRPC endpoint
        sampling_rate: 采样率 (0.0-1.0)
        console_export: 是否同时输出到控制台

    Returns:
        Tracer实例
    """
    # 从环境变量获取配置
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", otlp_endpoint)
    sampling_rate = float(os.getenv("TRACE_SAMPLING_RATE", sampling_rate))

    # 创建Resource（包含服务元信息）
    resource = Resource(
        attributes={
            SERVICE_NAME: service_name,
            "service.version": os.getenv("SERVICE_VERSION", "1.0.0"),
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        }
    )

    # 创建TracerProvider with采样器
    sampler = ParentBasedTraceIdRatio(sampling_rate)
    tracer_provider = TracerProvider(resource=resource, sampler=sampler)

    # OTLP导出器（支持Jaeger 1.35+）
    try:
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True,  # 开发环境不使用TLS
        )

        # 批处理Span导出器
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)

        logger.info(f"OTLP exporter configured: {otlp_endpoint}")
    except Exception as e:
        logger.error(f"Failed to configure OTLP exporter: {e}")

    # 控制台导出器（调试用）
    if console_export:
        console_exporter = ConsoleSpanExporter()
        console_processor = BatchSpanProcessor(console_exporter)
        tracer_provider.add_span_processor(console_processor)

    # 设置全局TracerProvider
    trace.set_tracer_provider(tracer_provider)

    logger.info(f"Tracing configured: service={service_name}, sampling_rate={sampling_rate}")

    # 返回Tracer
    return trace.get_tracer(service_name)


def instrument_app(app, service_name: str, otlp_endpoint: str = "http://localhost:4317", **kwargs):
    """
    自动插桩FastAPI应用.

    Args:
        app: FastAPI应用实例
        service_name: 服务名称
        otlp_endpoint: OTLP gRPC endpoint
        **kwargs: 传递给setup_tracing的额外参数
    """
    # 设置追踪
    setup_tracing(service_name, otlp_endpoint=otlp_endpoint, **kwargs)

    # FastAPI自动插桩
    FastAPIInstrumentor.instrument_app(app)

    # HTTP客户端插桩
    HTTPXClientInstrumentor().instrument()
    RequestsInstrumentor().instrument()

    # 数据库插桩
    try:
        SQLAlchemyInstrumentor().instrument()
    except Exception as e:
        logger.warning(f"Failed to instrument SQLAlchemy: {e}")

    # Redis插桩
    try:
        RedisInstrumentor().instrument()
    except Exception as e:
        logger.warning(f"Failed to instrument Redis: {e}")

    # 日志插桩（关联trace_id到日志）
    LoggingInstrumentor().instrument(set_logging_format=True)

    logger.info(f"Service '{service_name}' instrumented for tracing")


def get_current_span() -> trace.Span | None:
    """获取当前活跃的Span."""
    return trace.get_current_span()


def add_span_attributes(**attributes):
    """向当前Span添加属性."""
    span = get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def add_span_event(name: str, attributes: dict | None = None):
    """向当前Span添加事件."""
    span = get_current_span()
    if span and span.is_recording():
        span.add_event(name, attributes=attributes or {})


def record_exception(exception: Exception):
    """记录异常到当前Span."""
    span = get_current_span()
    if span and span.is_recording():
        span.record_exception(exception)


# 装饰器：为函数创建Span
def traced(name: str | None = None):
    """
    装饰器：为函数创建追踪Span.

    Args:
        name: Span名称，默认使用函数名

    Example:
        @traced("my_operation")
        def my_function():
            pass
    """

    def decorator(func):
        import functools

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(span_name):
                return func(*args, **kwargs)

        return wrapper

    return decorator
