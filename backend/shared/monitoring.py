"""
监控和日志模块.
提供应用监控、日志记录和性能追踪功能.
"""

import logging
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _create_placeholder_class(name):
    """创建单个占位类."""

    class PlaceholderClass:
        """空的占位类."""

        def __init__(self, *args, **kwargs):
            pass

        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

    PlaceholderClass.__name__ = name
    return PlaceholderClass


def _create_placeholder_classes():
    """创建占位类."""
    Counter = _create_placeholder_class("Counter")
    Histogram = _create_placeholder_class("Histogram")
    Gauge = _create_placeholder_class("Gauge")
    Summary = _create_placeholder_class("Summary")
    return Counter, Histogram, Gauge, Summary


# 尝试导入可选依赖
try:
    from prometheus_client import Counter, Gauge, Histogram, Summary

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter, Histogram, Gauge, Summary = _create_placeholder_classes()


try:
    import structlog

    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False


try:
    from opentelemetry import trace
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False

    # 创建空类作为替代
    class TracerProvider:
        def __init__(self):
            pass

    class BatchSpanProcessor:
        def __init__(self, *args, **kwargs):
            pass

    class ConsoleSpanExporter:
        def __init__(self):
            pass

    class JaegerExporter:
        def __init__(self, *args, **kwargs):
            pass

    class trace:
        @staticmethod
        def get_tracer(*args, **kwargs):
            return None


# 日志级别
class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class MetricData:
    """指标数据"""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    metric_type: str = "gauge"  # gauge, counter, histogram


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        self._metrics = defaultdict(list)
        self._counters = defaultdict(int)
        self._gauges = defaultdict(float)
        self._histograms = defaultdict(list)
        self._lock = threading.Lock()

        # 如果可用，初始化Prometheus指标
        if PROMETHEUS_AVAILABLE:
            self._init_prometheus_metrics()

    def _init_prometheus_metrics(self):
        """初始化Prometheus指标"""
        # 请求计数器
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )

        # 请求耗时直方图
        self.http_request_duration = Histogram("http_request_duration_seconds", "HTTP request duration")

        # 活跃连接数
        self.active_connections = Gauge("active_connections", "Number of active connections")

        # 服务健康状态
        self.service_health = Gauge("service_health", "Service health status", ["service"])

    def increment_counter(self, name: str, value: float = 1.0, labels: dict[str, str] = None):
        """增加计数器值"""
        with self._lock:
            if labels:
                key = (name, frozenset(labels.items()))
                self._counters[key] += value
            else:
                self._counters[name] += value

            # 如果可用，更新Prometheus指标
            if PROMETHEUS_AVAILABLE and name == "http_requests_total" and labels:
                self.http_requests_total.labels(**labels).inc(value)

    def set_gauge(self, name: str, value: float, labels: dict[str, str] = None):
        """设置仪表盘值"""
        with self._lock:
            if labels:
                key = (name, frozenset(labels.items()))
                self._gauges[key] = value
            else:
                self._gauges[name] = value

            # 如果可用，更新Prometheus指标
            if PROMETHEUS_AVAILABLE and name == "active_connections":
                if labels:
                    self.active_connections.labels(**labels).set(value)
                else:
                    self.active_connections.set(value)

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] = None):
        """记录直方图观察值"""
        with self._lock:
            if labels:
                key = (name, frozenset(labels.items()))
                self._histograms[key].append(value)
            else:
                self._histograms[name].append(value)

            # 如果可用，更新Prometheus指标
            if PROMETHEUS_AVAILABLE and name == "http_request_duration_seconds":
                if labels:
                    self.http_request_duration.labels(**labels).observe(value)
                else:
                    self.http_request_duration.observe(value)

    def get_metrics(self) -> list[MetricData]:
        """获取所有指标"""
        metrics = []

        with self._lock:
            # 获取计数器
            for (name, labels), value in self._counters.items():
                metrics.append(
                    MetricData(
                        name=name,
                        value=value,
                        labels=dict(labels) if labels else {},
                        metric_type="counter",
                    )
                )

            # 获取仪表盘
            for (name, labels), value in self._gauges.items():
                metrics.append(
                    MetricData(
                        name=name,
                        value=value,
                        labels=dict(labels) if labels else {},
                        metric_type="gauge",
                    )
                )

            # 获取直方图统计信息
            for (name, labels), values in self._histograms.items():
                if values:
                    metrics.append(
                        MetricData(
                            name=f"{name}_count",
                            value=len(values),
                            labels=dict(labels) if labels else {},
                            metric_type="counter",
                        )
                    )
                    metrics.append(
                        MetricData(
                            name=f"{name}_sum",
                            value=sum(values),
                            labels=dict(labels) if labels else {},
                            metric_type="counter",
                        )
                    )
                    metrics.append(
                        MetricData(
                            name=f"{name}_avg",
                            value=sum(values) / len(values),
                            labels=dict(labels) if labels else {},
                            metric_type="gauge",
                        )
                    )

        return metrics


class Logger:
    """增强的日志记录器"""

    def __init__(self, name: str, level: LogLevel = LogLevel.INFO):
        self.name = name
        self.level = level
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, level.value))

        # 如果可用，使用structlog
        if STRUCTLOG_AVAILABLE:
            self._logger = structlog.get_logger(name)

        # 添加控制台处理器
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        ch.setFormatter(formatter)

        self._logger.addHandler(ch)

    def debug(self, message: str, **kwargs):
        """记录调试信息"""
        if STRUCTLOG_AVAILABLE:
            self._logger.debug(message, **kwargs)
        else:
            self._logger.debug(message)

    def info(self, message: str, **kwargs):
        """记录信息"""
        if STRUCTLOG_AVAILABLE:
            self._logger.info(message, **kwargs)
        else:
            self._logger.info(message)

    def warning(self, message: str, **kwargs):
        """记录警告"""
        if STRUCTLOG_AVAILABLE:
            self._logger.warning(message, **kwargs)
        else:
            self._logger.warning(message)

    def error(self, message: str, **kwargs):
        """记录错误"""
        if STRUCTLOG_AVAILABLE:
            self._logger.error(message, **kwargs)
        else:
            self._logger.error(message)

    def critical(self, message: str, **kwargs):
        """记录严重错误"""
        if STRUCTLOG_AVAILABLE:
            self._logger.critical(message, **kwargs)
        else:
            self._logger.critical(message)


class DistributedTracer:
    """分布式追踪器"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._tracer = None

        if OPENTELEMETRY_AVAILABLE:
            self._init_tracer()

    def _init_tracer(self):
        """初始化追踪器"""
        # 设置追踪器提供者
        trace.set_tracer_provider(TracerProvider())

        # 创建控制台导出器
        console_exporter = ConsoleSpanExporter()

        # 创建批处理处理器
        span_processor = BatchSpanProcessor(console_exporter)

        # 添加处理器到追踪器
        trace.get_tracer_provider().add_span_processor(span_processor)

        # 如果配置了Jaeger，添加Jaeger导出器
        jaeger_host = os.getenv("JAEGER_HOST", "localhost")
        jaeger_port = int(os.getenv("JAEGER_PORT", "6831"))

        try:
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_host,
                agent_port=jaeger_port,
            )

            jaeger_processor = BatchSpanProcessor(jaeger_exporter)
            trace.get_tracer_provider().add_span_processor(jaeger_processor)
        except Exception as e:
            logging.warning(f"无法连接到Jaeger: {e}")

        # 获取追踪器
        self._tracer = trace.get_tracer(self.service_name)

    def start_span(self, name: str, attributes: dict[str, str] = None) -> Any:
        """开始一个新的追踪span"""
        if self._tracer:
            return self._tracer.start_span(name, attributes=attributes or {})
        return None

    def get_current_span(self) -> Any:
        """获取当前span"""
        if OPENTELEMETRY_AVAILABLE:
            return trace.get_current_span()
        return None


class MonitoringService:
    """监控服务"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.metrics = MetricsCollector()
        self.logger = Logger(service_name)
        self.tracer = DistributedTracer(service_name)

        # 性能数据缓存
        self._performance_data = defaultdict(lambda: deque(maxlen=100))

        # 健康状态
        self._health_status = "healthy"

    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """记录请求指标"""
        # 记录计数器
        self.metrics.increment_counter(
            "http_requests_total",
            labels={"method": method, "endpoint": endpoint, "status": str(status_code)},
        )

        # 记录耗时
        self.metrics.observe_histogram(
            "http_request_duration_seconds",
            duration,
            labels={"method": method, "endpoint": endpoint},
        )

        # 记录性能数据
        self._performance_data[f"{method}:{endpoint}"].append(
            {"timestamp": time.time(), "duration": duration, "status": status_code}
        )

    def get_performance_summary(self, time_range: int = 3600) -> dict[str, Any]:
        """获取性能摘要"""
        now = time.time()
        summary = {
            "service": self.service_name,
            "timestamp": now,
            "time_range": time_range,
            "requests": {},
            "endpoints": {},
        }

        # 计算各端点的性能指标
        for endpoint, data in self._performance_data.items():
            # 过滤时间范围内的数据
            recent_data = [d for d in data if now - d["timestamp"] <= time_range]

            if not recent_data:
                continue

            durations = [d["duration"] for d in recent_data]
            statuses = [d["status"] for d in recent_data]

            summary["endpoints"][endpoint] = {
                "count": len(recent_data),
                "avg_duration": sum(durations) / len(durations),
                "max_duration": max(durations),
                "min_duration": min(durations),
                "status_distribution": {str(status): statuses.count(status) for status in set(statuses)},
            }

        # 计算总体请求统计
        total_requests = sum([data["count"] for data in summary["endpoints"].values()])
        total_duration = sum([data["avg_duration"] * data["count"] for data in summary["endpoints"].values()])

        summary["requests"] = {
            "total": total_requests,
            "avg_duration": (total_duration / total_requests if total_requests > 0 else 0),
        }

        return summary

    def record_health_status(self, status: str):
        """记录健康状态"""
        self._health_status = status
        self.metrics.set_gauge(
            "service_health",
            1.0 if status == "healthy" else 0.0,
            {"service": self.service_name},
        )

    def get_health_status(self) -> dict[str, Any]:
        """获取健康状态"""
        return {
            "service": self.service_name,
            "status": self._health_status,
            "timestamp": time.time(),
        }

    def trace_request(self, name: str, **kwargs):
        """追踪请求"""
        span = self.tracer.start_span(name)
        if span:
            for key, value in kwargs.items():
                span.set_attribute(key, value)
            return span
        return None


# 全局监控服务实例
_monitoring_services: dict[str, MonitoringService] = {}


def get_monitoring_service(service_name: str) -> MonitoringService:
    """获取监控服务实例"""
    if service_name not in _monitoring_services:
        _monitoring_services[service_name] = MonitoringService(service_name)
    return _monitoring_services[service_name]
