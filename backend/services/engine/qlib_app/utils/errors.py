"""统一错误处理模块

提供:
1. 错误码定义
2. 错误消息映射
3. 异常类定义
4. 错误响应格式化
"""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel


class ErrorCode(str, Enum):
    """错误码枚举"""

    # 通用错误 (1xxx)
    UNKNOWN_ERROR = "1000"
    INVALID_PARAMETER = "1001"
    MISSING_PARAMETER = "1002"
    VALIDATION_ERROR = "1003"

    # Qlib相关错误 (2xxx)
    QLIB_NOT_INITIALIZED = "2001"
    QLIB_INIT_FAILED = "2002"
    QLIB_DATA_NOT_AVAILABLE = "2003"
    QLIB_STRATEGY_ERROR = "2004"
    QLIB_EXECUTOR_ERROR = "2005"
    QLIB_BACKTEST_FAILED = "2006"

    # 数据相关错误 (3xxx)
    DATA_NOT_FOUND = "3001"
    DATA_DOWNLOAD_FAILED = "3002"
    DATA_FORMAT_ERROR = "3003"
    STOCK_NOT_FOUND = "3004"
    DATE_RANGE_INVALID = "3005"

    # 策略相关错误 (4xxx)
    STRATEGY_NOT_FOUND = "4001"
    STRATEGY_SYNTAX_ERROR = "4002"
    STRATEGY_VALIDATION_FAILED = "4003"
    STRATEGY_EXECUTION_ERROR = "4004"
    STRATEGY_TYPE_UNSUPPORTED = "4005"

    # 回测相关错误 (5xxx)
    BACKTEST_NOT_FOUND = "5001"
    BACKTEST_ALREADY_RUNNING = "5002"
    BACKTEST_TIMEOUT = "5003"
    BACKTEST_CANCELLED = "5004"
    BACKTEST_INSUFFICIENT_DATA = "5005"

    # 资源相关错误 (6xxx)
    RESOURCE_NOT_FOUND = "6001"
    RESOURCE_EXHAUSTED = "6002"
    RATE_LIMIT_EXCEEDED = "6003"
    DISK_SPACE_FULL = "6004"

    # 权限相关错误 (7xxx)
    UNAUTHORIZED = "7001"
    FORBIDDEN = "7002"
    ACCESS_DENIED = "7003"

    # 错误消息映射（中文）


ERROR_MESSAGES = {
    # 通用错误
    ErrorCode.UNKNOWN_ERROR: "未知错误，请联系技术支持",
    ErrorCode.INVALID_PARAMETER: "参数无效",
    ErrorCode.MISSING_PARAMETER: "缺少必需参数",
    ErrorCode.VALIDATION_ERROR: "数据验证失败",
    # Qlib相关
    ErrorCode.QLIB_NOT_INITIALIZED: "Qlib服务未初始化，请稍后重试",
    ErrorCode.QLIB_INIT_FAILED: "Qlib初始化失败，请检查配置",
    ErrorCode.QLIB_DATA_NOT_AVAILABLE: "Qlib数据不可用，请先下载数据",
    ErrorCode.QLIB_STRATEGY_ERROR: "Qlib策略配置错误",
    ErrorCode.QLIB_EXECUTOR_ERROR: "Qlib执行器错误",
    ErrorCode.QLIB_BACKTEST_FAILED: "Qlib回测执行失败",
    # 数据相关
    ErrorCode.DATA_NOT_FOUND: "数据不存在",
    ErrorCode.DATA_DOWNLOAD_FAILED: "数据下载失败",
    ErrorCode.DATA_FORMAT_ERROR: "数据格式错误",
    ErrorCode.STOCK_NOT_FOUND: "股票代码不存在",
    ErrorCode.DATE_RANGE_INVALID: "日期范围无效",
    # 策略相关
    ErrorCode.STRATEGY_NOT_FOUND: "策略不存在",
    ErrorCode.STRATEGY_SYNTAX_ERROR: "策略代码语法错误",
    ErrorCode.STRATEGY_VALIDATION_FAILED: "策略验证失败",
    ErrorCode.STRATEGY_EXECUTION_ERROR: "策略执行错误",
    ErrorCode.STRATEGY_TYPE_UNSUPPORTED: "不支持的策略类型",
    # 回测相关
    ErrorCode.BACKTEST_NOT_FOUND: "回测记录不存在",
    ErrorCode.BACKTEST_ALREADY_RUNNING: "回测已在运行中",
    ErrorCode.BACKTEST_TIMEOUT: "回测执行超时",
    ErrorCode.BACKTEST_CANCELLED: "回测已取消",
    ErrorCode.BACKTEST_INSUFFICIENT_DATA: "数据不足，无法执行回测",
    # 资源相关
    ErrorCode.RESOURCE_NOT_FOUND: "资源不存在",
    ErrorCode.RESOURCE_EXHAUSTED: "资源耗尽",
    ErrorCode.RATE_LIMIT_EXCEEDED: "请求频率超限，请稍后重试",
    ErrorCode.DISK_SPACE_FULL: "磁盘空间不足",
    # 权限相关
    ErrorCode.UNAUTHORIZED: "未授权，请先登录",
    ErrorCode.FORBIDDEN: "无权限访问",
    ErrorCode.ACCESS_DENIED: "访问被拒绝",
}


class BacktestError(Exception):
    """回测业务异常基类"""

    def __init__(
        self,
        code: ErrorCode,
        message: str = None,
        details: dict[str, Any] = None,
    ):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "未知错误")
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "error_code": self.code,
            "error_message": self.message,
            "details": self.details,
        }


class ErrorResponse(BaseModel):
    """统一错误响应格式"""

    success: bool = False
    error_code: str
    error_message: str
    details: dict[str, Any] | None = None
    timestamp: str | None = None

    @classmethod
    def from_exception(cls, exc: BacktestError):
        """从异常创建响应"""
        from datetime import datetime

        return cls(
            error_code=exc.code,
            error_message=exc.message,
            details=exc.details,
            timestamp=datetime.now().isoformat(),
        )


def get_error_message(code: ErrorCode, **kwargs) -> str:
    """获取错误消息（支持格式化）"""
    message = ERROR_MESSAGES.get(code, "未知错误")
    if kwargs:
        try:
            message = message.format(**kwargs)
        except KeyError:
            pass
    return message

    # 便捷异常类


class QlibNotInitializedError(BacktestError):
    def __init__(self, details=None):
        super().__init__(ErrorCode.QLIB_NOT_INITIALIZED, details=details)


class QlibDataNotAvailableError(BacktestError):
    def __init__(self, details=None):
        super().__init__(ErrorCode.QLIB_DATA_NOT_AVAILABLE, details=details)


class StrategyNotFoundError(BacktestError):
    def __init__(self, strategy_id: str = None, details=None):
        msg = f"策略不存在: {strategy_id}" if strategy_id else None
        super().__init__(ErrorCode.STRATEGY_NOT_FOUND, message=msg, details=details)


class StrategyValidationError(BacktestError):
    def __init__(self, errors: list, details=None):
        details = details or {}
        details["validation_errors"] = errors
        super().__init__(ErrorCode.STRATEGY_VALIDATION_FAILED, details=details)


class BacktestNotFoundError(BacktestError):
    def __init__(self, backtest_id: str, details=None):
        msg = f"回测记录不存在: {backtest_id}"
        super().__init__(ErrorCode.BACKTEST_NOT_FOUND, message=msg, details=details)


class DataRangeInvalidError(BacktestError):
    def __init__(self, start_date: str, end_date: str, details=None):
        msg = f"日期范围无效: {start_date} ~ {end_date}"
        super().__init__(ErrorCode.DATE_RANGE_INVALID, message=msg, details=details)
