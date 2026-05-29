"""
标准化数据操作基类

提供统一的数据操作接口，集成日志、追踪和错误处理。
"""

import logging
import sys
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# 添加路径以便导入共享模块
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app/backend/shared")

# 导入共享模块
try:
    from backend.shared.config import settings
    from backend.shared.database import engine as _shared_engine
    from backend.shared.observability.logging import (
        LoggerMixin,
        init_service_logging,
        log_performance,
    )
    from backend.shared.observability.tracing import trace_function
except ImportError as e:
    # 如果无法导入，使用简单的替代实现
    print(f"Warning: Could not import shared modules: {e}")
    init_service_logging = None
    LoggerMixin = None
    log_performance = None
    trace_function = None
    settings = None
    _shared_engine = None

    # 创建fallback装饰器


def fallback_performance_decorator(logger, operation_name):
    """Fallback performance decorator when observability modules are not available"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator

    # 使用fallback装饰器如果log_performance不可用


if log_performance is None:
    log_performance = fallback_performance_decorator


class BaseDataOperation(ABC):
    """
    数据操作基类

    提供统一的数据操作接口，包括：
    - 标准化日志记录
    - 性能监控
    - 错误处理
    - 配置管理
    """

    def __init__(self, operation_name: str, config: dict[str, Any] | None = None, **kwargs):
        """
        初始化数据操作

        Args:
            operation_name: 操作名称
            config: 配置字典
            **kwargs: 其他参数
        """
        self.operation_name = operation_name
        self.config = config or {}
        self.start_time = None
        self.operation_id = str(uuid.uuid4())[:8]

        # 初始化日志
        if init_service_logging and settings:
            self.logger = init_service_logging(
                service_name=f"data-{operation_name}",
                service_version="1.0.0",
                log_level=settings.app.log_level,
            )
        else:
            self.logger = logging.getLogger(f"data.{operation_name}")

        self.logger.info(
            f"Data operation initialized: {operation_name}",
            extra={
                "operation_id": self.operation_id,
                "operation_name": operation_name,
                "config_keys": list(self.config.keys()),
            },
        )

    @log_performance(None, "execute_operation")
    def execute(self, **kwargs) -> dict[str, Any]:
        """
        执行数据操作

        Args:
            **kwargs: 操作参数

        Returns:
            操作结果字典
        """
        self.start_time = time.time()

        self.logger.info(
            "Starting data operation",
            extra={
                "operation_id": self.operation_id,
                "operation_name": self.operation_name,
                "parameters": kwargs,
            },
        )

        try:
            # 执行具体操作
            result = self._execute_operation(**kwargs)

            # 计算执行时间
            execution_time = time.time() - self.start_time

            # 记录成功
            self.logger.info(
                "Data operation completed successfully",
                extra={
                    "operation_id": self.operation_id,
                    "operation_name": self.operation_name,
                    "execution_time": round(execution_time, 4),
                    "result_summary": self._summarize_result(result),
                },
            )

            # 添加操作元数据
            result.update(
                {
                    "operation_id": self.operation_id,
                    "operation_name": self.operation_name,
                    "execution_time": round(execution_time, 4),
                    "completed_at": datetime.now().isoformat(),
                }
            )

            return result

        except Exception as e:
            execution_time = time.time() - self.start_time

            # 记录错误
            self.logger.error(
                "Data operation failed",
                extra={
                    "operation_id": self.operation_id,
                    "operation_name": self.operation_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "execution_time": round(execution_time, 4),
                },
            )

            # 返回错误结果
            return {
                "operation_id": self.operation_id,
                "operation_name": self.operation_name,
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time": round(execution_time, 4),
                "completed_at": datetime.now().isoformat(),
            }

    @abstractmethod
    def _execute_operation(self, **kwargs) -> dict[str, Any]:
        """
        执行具体的数据操作（子类实现）

        Args:
            **kwargs: 操作参数

        Returns:
            操作结果字典
        """

    def _summarize_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """
        总结操作结果

        Args:
            result: 操作结果

        Returns:
            结果摘要
        """
        summary = {}

        # 提取关键指标
        if "records_processed" in result:
            summary["records_processed"] = result["records_processed"]
        if "records_updated" in result:
            summary["records_updated"] = result["records_updated"]
        if "records_inserted" in result:
            summary["records_inserted"] = result["records_inserted"]
        if "success" in result:
            summary["success"] = result["success"]

        return summary

    def validate_parameters(self, required_params: list[str], **kwargs) -> bool:
        """
        验证必需参数

        Args:
            required_params: 必需参数列表
            **kwargs: 传入参数

        Returns:
            验证是否通过
        """
        missing_params = [param for param in required_params if param not in kwargs]

        if missing_params:
            self.logger.error(
                "Missing required parameters",
                extra={
                    "operation_id": self.operation_id,
                    "missing_params": missing_params,
                    "provided_params": list(kwargs.keys()),
                },
            )
            return False

        return True

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        return self.config.get(key, default)


class DatabaseDataOperation(BaseDataOperation):
    """
    数据库数据操作基类
    """

    def __init__(self, operation_name: str, config: dict[str, Any] | None = None):
        super().__init__(operation_name, config)
        self.db_connection = None

    def connect_to_database(self) -> bool:
        """
        连接到数据库

        Returns:
            连接是否成功
        """
        try:
            # 这里应该使用统一的数据库连接
            # 暂时使用占位符
            self.db_connection = "database_connection_placeholder"

            self.logger.info(
                "Database connection established",
                extra={"operation_id": self.operation_id},
            )
            return True

        except Exception as e:
            self.logger.error(
                "Failed to connect to database",
                extra={"operation_id": self.operation_id, "error": str(e)},
            )
            return False

    def close_database_connection(self):
        """关闭数据库连接"""
        if self.db_connection:
            # 关闭连接的逻辑
            self.db_connection = None

            self.logger.info("Database connection closed", extra={"operation_id": self.operation_id})


class FileDataOperation(BaseDataOperation):
    """
    文件数据操作基类
    """

    def __init__(self, operation_name: str, config: dict[str, Any] | None = None):
        super().__init__(operation_name, config)
        self.file_path = None

    def set_file_path(self, file_path: str | Path) -> bool:
        """
        设置文件路径

        Args:
            file_path: 文件路径

        Returns:
            设置是否成功
        """
        try:
            self.file_path = Path(file_path)

            if not self.file_path.exists():
                self.logger.warning(
                    "File does not exist",
                    extra={
                        "operation_id": self.operation_id,
                        "file_path": str(self.file_path),
                    },
                )
                return False

            self.logger.info(
                "File path set successfully",
                extra={
                    "operation_id": self.operation_id,
                    "file_path": str(self.file_path),
                    "file_size": self.file_path.stat().st_size,
                },
            )
            return True

        except Exception as e:
            self.logger.error(
                "Failed to set file path",
                extra={
                    "operation_id": self.operation_id,
                    "file_path": str(file_path),
                    "error": str(e),
                },
            )
            return False
