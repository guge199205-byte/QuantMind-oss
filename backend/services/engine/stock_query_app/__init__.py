#!/usr/bin/env python3
"""
股票查询模块
提供股票数据查询功能，支持本地数据库和Tushare数据源
"""

from .models import (
    AdjustType,
    DataFrequency,
    HistoricalQueryRequest,
    HistoricalQuote,
    MarketType,
    QueryResponse,
    RealtimeQueryRequest,
    RealtimeQuote,
    SearchRequest,
    StockInfo,
    TechnicalIndicator,
    TechnicalIndicatorRequest,
    TradeStatus,
)
from .routes import router as stock_router
from .services import StockQueryService, StockSearchService

__version__ = "2.0.0"
__author__ = "QuantMind Team"
__description__ = "股票查询模块 - 支持本地数据库和Tushare数据源"

__all__ = [
    # 数据模型
    "StockInfo",
    "RealtimeQuote",
    "HistoricalQuote",
    "TechnicalIndicator",
    "SearchRequest",
    "RealtimeQueryRequest",
    "HistoricalQueryRequest",
    "TechnicalIndicatorRequest",
    "QueryResponse",
    # 枚举类型
    "MarketType",
    "TradeStatus",
    "AdjustType",
    "DataFrequency",
    # 服务类
    "StockQueryService",
    "StockSearchService",
    # FastAPI路由
    "stock_router",
]
