"""
统一结构化日志模块

提供标准化的日志格式和配置，支持分布式追踪集成。
所有服务都应该使用此模块进行日志记录。

Features:
- 结构化JSON日志格式
- 自动集成trace_id和span_id
- 支持多种输出格式
- 性能优化的异步日志
- 环境感知配置

Author: QuantMind Team
Version: 1.0.0
"""

import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from opentelemetry import trace

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""

    def __init__(
        self,
        service_name: str,
        service_version: str = "1.0.0",
        include_trace: bool = True,
        extra_fields: dict[str, Any] | None = None,
    ):
        """
        初始化结构化格式化器

        Args:
            service_name: 服务名称
            service_version: 服务版本
            include_trace: 是否包含追踪信息
            extra_fields: 额外的固定字段
        """
        super().__init__()
        self.service_name = service_name
        self.service_version = service_version
        self.include_trace = include_trace
        self.extra_fields = extra_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON结构"""

        # 基础日志信息
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "service": self.service_name,
            "service_version": self.service_version,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread_id": record.thread,
            "process_id": record.process,
        }

        # 添加追踪信息
        if self.include_trace and _OTEL_AVAILABLE:
            try:
                span = trace.get_current_span()
                if span and span.is_recording():
                    span_context = span.get_span_context()
                    log_data.update(
                        {
                            "trace_id": format(span_context.trace_id, "032x"),
                            "span_id": format(span_context.span_id, "016x"),
                            "trace_flags": span_context.trace_flags,
                        }
                    )
            except Exception:
                # 追踪信息获取失败时不影响日志记录
                pass

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # 添加额外字段
        log_data.update(self.extra_fields)

        # 添加记录级别的额外属性
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "metadata"):
            log_data["metadata"] = record.metadata

        return json.dumps(log_data, ensure_ascii=False, default=str)


class QuantMindLogger:
    """QuantMind统一日志管理器"""

    _loggers: dict[str, logging.Logger] = {}
    _configured = False

    @classmethod
    def configure(
        cls,
        service_name: str,
        service_version: str = "1.0.0",
        log_level: str = "INFO",
        log_format: str = "json",  # json or console
        log_file: str | None = None,
        include_trace: bool = True,
        extra_fields: dict[str, Any] | None = None,
    ) -> None:
        """
        配置全局日志设置

        Args:
            service_name: 服务名称
            service_version: 服务版本
            log_level: 日志级别
            log_format: 日志格式 (json/console)
            log_file: 日志文件路径
            include_trace: 是否包含追踪信息
            extra_fields: 额外的固定字段
        """
        if cls._configured:
            return

        # 获取根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))

        # 清除现有处理器
        root_logger.handlers.clear()

        # 创建格式化器
        if log_format.lower() == "json":
            formatter = StructuredFormatter(
                service_name=service_name,
                service_version=service_version,
                include_trace=include_trace,
                extra_fields=extra_fields,
            )
        else:
            # 控制台格式
            formatter = logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        root_logger.addHandler(console_handler)

        # 文件处理器（如果指定）
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            file_handler.setLevel(getattr(logging, log_level.upper()))
            root_logger.addHandler(file_handler)

        cls._configured = True

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        获取日志器实例

        Args:
            name: 日志器名称

        Returns:
            日志器实例
        """
        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)
        return cls._loggers[name]

    @classmethod
    def log_with_context(
        cls,
        logger: logging.Logger,
        level: str,
        message: str,
        duration_ms: float | None = None,
        user_id: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """
        带上下文的日志记录

        Args:
            logger: 日志器实例
            level: 日志级别
            message: 日志消息
            duration_ms: 执行时间（毫秒）
            user_id: 用户ID
            request_id: 请求ID
            metadata: 元数据字典
            **kwargs: 其他额外字段
        """
        # 创建日志记录
        extra = {}

        if duration_ms is not None:
            extra["duration_ms"] = duration_ms

        if user_id is not None:
            extra["user_id"] = user_id

        if request_id is not None:
            extra["request_id"] = request_id

        if metadata is not None:
            extra["metadata"] = metadata

        extra.update(kwargs)

        # 记录日志
        log_level = getattr(logging, level.upper())
        logger.log(log_level, message, extra=extra)


class LoggerMixin:
    """日志器混入类，为其他类提供日志功能"""

    @property
    def logger(self) -> logging.Logger:
        """获取当前类的日志器"""
        return QuantMindLogger.get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    def log_info(
        self,
        message: str,
        duration_ms: float | None = None,
        user_id: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """记录INFO级别日志"""
        QuantMindLogger.log_with_context(
            self.logger,
            "INFO",
            message,
            duration_ms,
            user_id,
            request_id,
            metadata,
            **kwargs,
        )

    def log_error(
        self,
        message: str,
        duration_ms: float | None = None,
        user_id: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """记录ERROR级别日志"""
        QuantMindLogger.log_with_context(
            self.logger,
            "ERROR",
            message,
            duration_ms,
            user_id,
            request_id,
            metadata,
            **kwargs,
        )

    def log_warning(
        self,
        message: str,
        duration_ms: float | None = None,
        user_id: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """记录WARNING级别日志"""
        QuantMindLogger.log_with_context(
            self.logger,
            "WARNING",
            message,
            duration_ms,
            user_id,
            request_id,
            metadata,
            **kwargs,
        )

    def log_debug(
        self,
        message: str,
        duration_ms: float | None = None,
        user_id: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """记录DEBUG级别日志"""
        QuantMindLogger.log_with_context(
            self.logger,
            "DEBUG",
            message,
            duration_ms,
            user_id,
            request_id,
            metadata,
            **kwargs,
        )


def init_service_logging(
    service_name: str,
    service_version: str = "1.0.0",
    log_level: str | None = None,
    log_file: str | None = None,
) -> logging.Logger:
    """
    初始化服务日志

    Args:
        service_name: 服务名称
        service_version: 服务版本
        log_level: 日志级别（从环境变量获取）
        log_file: 日志文件路径

    Returns:
        配置好的日志器实例
    """
    # 从环境变量获取配置
    env_log_level = log_level or os.getenv("LOG_LEVEL", "INFO")
    env_log_format = os.getenv("LOG_FORMAT", "json")
    env_log_file = log_file or os.getenv("LOG_FILE")

    # 配置日志
    QuantMindLogger.configure(
        service_name=service_name,
        service_version=service_version,
        log_level=env_log_level,
        log_format=env_log_format,
        log_file=env_log_file,
        include_trace=True,
        extra_fields={
            "environment": os.getenv("ENVIRONMENT", "development"),
            "deployment": os.getenv("DEPLOYMENT", "local"),
        },
    )

    return QuantMindLogger.get_logger(service_name)


# 性能监控装饰器
def log_performance(logger: logging.Logger | None = None):
    """
    性能监控装饰器

    Args:
        logger: 日志器实例，如果为None则使用函数所在类的日志器
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            func_name = f"{func.__module__}.{func.__name__}"

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                # 记录性能日志
                if logger:
                    QuantMindLogger.log_with_context(
                        logger,
                        "INFO",
                        f"Function {func_name} executed successfully",
                        duration_ms=duration_ms,
                        metadata={"function": func_name, "success": True},
                    )
                else:
                    # 尝试从args中获取self来获取logger
                    if args and hasattr(args[0], "log_info"):
                        args[0].log_info(
                            f"Function {func_name} executed successfully",
                            duration_ms=duration_ms,
                            metadata={"function": func_name, "success": True},
                        )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                # 记录错误日志
                if logger:
                    QuantMindLogger.log_with_context(
                        logger,
                        "ERROR",
                        f"Function {func_name} failed: {str(e)}",
                        duration_ms=duration_ms,
                        metadata={
                            "function": func_name,
                            "success": False,
                            "error": str(e),
                        },
                    )
                else:
                    if args and hasattr(args[0], "log_error"):
                        args[0].log_error(
                            f"Function {func_name} failed: {str(e)}",
                            duration_ms=duration_ms,
                            metadata={
                                "function": func_name,
                                "success": False,
                                "error": str(e),
                            },
                        )

                raise

        return wrapper

    return decorator


__all__ = [
    "QuantMindLogger",
    "LoggerMixin",
    "init_service_logging",
    "log_performance",
    "StructuredFormatter",
]
