"""
数据源适配器抽象基类 + 异常体系。

设计原则：
1. 所有离线数据源（baostock / efinance / qstock / tdx-api / akshare / ...）
   继承 OfflineDataSourceAdapter，实现统一签名。
2. 字段缺失返回 DataUnavailable，由 FieldAggregator 决定是否切换备用源。
3. 限流由适配器内部处理，并通过 SourceRateLimited 通知聚合层退避。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Iterable, Optional

import pandas as pd


# ---------------------------------------------------------------------------
# 异常体系
# ---------------------------------------------------------------------------
class DataPlatformException(Exception):
    """数据平台所有异常的基类。"""


class DataUnavailable(DataPlatformException):
    """该数据源/字段对当前 symbol+日期范围无数据。聚合层会尝试 fallback。"""


class InvalidFieldRequest(DataPlatformException):
    """请求的字段在该市场/源上未定义。"""


class SourceRateLimited(DataPlatformException):
    """数据源限流。聚合层应记录并切换或退避。"""


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------
class OfflineDataSourceAdapter(ABC):
    """离线/历史数据源统一接口。

    子类必须声明：
        name    : 唯一标识（如 "baostock", "efinance"）
        markets : 支持的市场列表，元素取值 "A" / "HK" / "US"
        fields  : 支持的字段集合（参考 config/data_sources/field_routing.yaml）

    可选实现：
        fetch_realtime(symbol)  - 实时行情快照
        fetch_minute(symbol, ..) - 分钟线
        fetch_tick(symbol, ..)   - 逐笔
    """

    name: str = ""
    markets: list[str] = []
    fields: set[str] = set()

    # ---- 必选 ----
    @abstractmethod
    def fetch_daily(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取日线 OHLCV。

        返回 DataFrame 必须包含 OHLCV_COLUMNS 中的核心列；
        无数据时抛 DataUnavailable，不要返回空 DataFrame。
        """

    @abstractmethod
    def fetch_meta(self, market: str) -> pd.DataFrame:
        """获取该市场的标的清单（symbol/name/exchange/list_date/delist_date 等）。"""

    # ---- 可选 ----
    def fetch_realtime(self, symbol: str) -> Optional[dict[str, Any]]:
        raise InvalidFieldRequest(f"{self.name} 不支持 realtime")

    def fetch_minute(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        freq: str = "1min",
    ) -> pd.DataFrame:
        raise InvalidFieldRequest(f"{self.name} 不支持 minute({freq})")

    def fetch_tick(self, symbol: str, trade_date: date) -> pd.DataFrame:
        raise InvalidFieldRequest(f"{self.name} 不支持 tick")

    def fetch_field(
        self,
        field: str,
        symbol: str,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """通用字段拉取入口，未覆盖的字段抛 InvalidFieldRequest。"""
        raise InvalidFieldRequest(f"{self.name} 未实现 field={field}")

    # ---- 通用工具 ----
    def supports(self, field: str, market: str) -> bool:
        return market in self.markets and (not self.fields or field in self.fields)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} markets={self.markets}>"
