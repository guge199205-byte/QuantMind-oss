"""
QuantMind 数据平台 (Data Platform)

字段聚合层：统一多市场（A/HK/US）多数据源的接入、清洗、路由、监控。

模块组成：
- base       : OfflineDataSourceAdapter 抽象基类 + 异常体系
- registry   : 数据源注册中心
- models     : 标准化的数据模型与列定义
- storage    : Parquet / Qlib bin 存储写出
- monitor    : 数据源健康监控（Redis 指标）
- calendars/ : 各市场交易日历
- adapters/  : 具体数据源适配器（D3/D4 实现）
"""

from backend.services.engine.data_platform.base import (
    DataPlatformException,
    DataUnavailable,
    InvalidFieldRequest,
    OfflineDataSourceAdapter,
    SourceRateLimited,
)
from backend.services.engine.data_platform.models import (
    OHLCV_COLUMNS,
    FUNDAMENTAL_COLUMNS,
    SYMBOL_META_COLUMNS,
    FundamentalRow,
    OHLCVRow,
    RealtimeQuote,
    SymbolMeta,
)
from backend.services.engine.data_platform.registry import (
    SourceRegistry,
    get_registry,
)

__all__ = [
    "OfflineDataSourceAdapter",
    "DataPlatformException",
    "DataUnavailable",
    "InvalidFieldRequest",
    "SourceRateLimited",
    "OHLCVRow",
    "FundamentalRow",
    "SymbolMeta",
    "RealtimeQuote",
    "OHLCV_COLUMNS",
    "FUNDAMENTAL_COLUMNS",
    "SYMBOL_META_COLUMNS",
    "SourceRegistry",
    "get_registry",
]
