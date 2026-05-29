"""
标准化数据操作模块

提供统一的数据操作接口，包括：
- 基础数据操作类
- 股票数据更新器
- 数据验证器
- 脚本运行器
"""

from .base import BaseDataOperation, DatabaseDataOperation, FileDataOperation
from .data_validator import (
    DataValidator,
    validate_stock_data,
    ValidationResult,
    ValidationRule,
)
from .runner import (
    create_sample_config,
    DataScriptRunner,
    run_data_scripts,
    TaskConfig,
    TaskResult,
)
from .stock_data_updater import StockDataUpdater, update_stock_data

__all__ = [
    # Base classes
    "BaseDataOperation",
    "DatabaseDataOperation",
    "FileDataOperation",
    # Stock data operations
    "StockDataUpdater",
    "update_stock_data",
    # Data validation
    "DataValidator",
    "validate_stock_data",
    "ValidationResult",
    "ValidationRule",
    # Script runner
    "DataScriptRunner",
    "run_data_scripts",
    "create_sample_config",
    "TaskConfig",
    "TaskResult",
]
