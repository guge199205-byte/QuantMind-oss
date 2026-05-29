#!/usr/bin/env python3
"""
配置模块初始化文件
使config目录成为一个Python包
"""

# 版本信息
__version__ = "1.0.0"
__author__ = "QuantMind Team"
__description__ = "Configuration management for QuantMind"

# 导入主要配置管理器
try:
    from .database_manager import DatabaseManager
    from .unified_config_manager import UnifiedConfigManager
except ImportError:
    # 如果某些模块不存在，忽略导入错误
    pass

__all__ = ["DatabaseManager", "UnifiedConfigManager"]
