"""
easyquotation adapter — A 股实时行情

使用 easyquotation 库获取新浪/通达信实时行情。
仅支持 realtime_quote 字段，market = A。
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import pandas as pd

from backend.services.engine.data_platform.base import (
    DataUnavailable,
    InvalidFieldRequest,
    OfflineDataSourceAdapter,
)

logger = logging.getLogger(__name__)

try:
    import easyquotation  # type: ignore
    _EQ_AVAILABLE = True
except ImportError:
    _EQ_AVAILABLE = False


class EasyQuotationAdapter(OfflineDataSourceAdapter):
    name = "easyquotation"
    markets = ["A"]
    fields = {"realtime_quote"}

    def __init__(self):
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return
        if not _EQ_AVAILABLE:
            raise DataUnavailable("easyquotation not installed")
        self._client = easyquotation.use("sina")

    def fetch_daily(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        raise InvalidFieldRequest("easyquotation 仅支持 realtime_quote，不支持日 K 线")

    def fetch_meta(self, market: str) -> pd.DataFrame:
        raise InvalidFieldRequest("easyquotation 不支持 fetch_meta")

    def fetch_field(
        self,
        field: str,
        symbol: str,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
        **kwargs,
    ) -> pd.DataFrame:
        if field != "realtime_quote":
            raise InvalidFieldRequest(f"easyquotation: field={field} 不支持")

        self._ensure_client()

        # 标准化代码：移除 .SH/.SZ 后缀
        code = symbol.strip().upper()
        for suffix in (".SH", ".SZ", ".BJ"):
            code = code.replace(suffix, "")

        try:
            result = self._client.real(code)
            if code not in result:
                raise DataUnavailable(f"easyquotation: {symbol} 无数据")
            d = result[code]
            return pd.DataFrame([{
                "symbol": symbol.upper(),
                "name": d.get("name", ""),
                "price": d.get("price", 0),
                "open": d.get("open", 0),
                "high": d.get("high", 0),
                "low": d.get("low", 0),
                "volume": d.get("volume", 0),
                "amount": d.get("amount", 0),
                "bid1": d.get("bid1", 0),
                "ask1": d.get("ask1", 0),
                "source": self.name,
            }])
        except DataUnavailable:
            raise
        except Exception as exc:
            raise DataUnavailable(f"easyquotation 获取 {symbol} 失败: {exc}") from exc

    def fetch_realtime(self, symbols: list[str]) -> pd.DataFrame:
        """批量获取实时行情。"""
        self._ensure_client()

        codes = []
        for s in symbols:
            code = s.strip().upper()
            for suffix in (".SH", ".SZ", ".BJ"):
                code = code.replace(suffix, "")
            codes.append(code)

        try:
            result = self._client.real(codes)
            rows = []
            for orig, code in zip(symbols, codes):
                if code in result:
                    d = result[code]
                    rows.append({
                        "symbol": orig.upper(),
                        "name": d.get("name", ""),
                        "price": d.get("price", 0),
                        "open": d.get("open", 0),
                        "high": d.get("high", 0),
                        "low": d.get("low", 0),
                        "volume": d.get("volume", 0),
                        "amount": d.get("amount", 0),
                        "source": self.name,
                    })
            if not rows:
                raise DataUnavailable("easyquotation: 所有代码均无数据")
            return pd.DataFrame(rows)
        except DataUnavailable:
            raise
        except Exception as exc:
            raise DataUnavailable(f"easyquotation 批量获取失败: {exc}") from exc


def register() -> bool:
    if not _EQ_AVAILABLE:
        logger.info("easyquotation 未安装，跳过 EasyQuotationAdapter 注册")
        return False
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(EasyQuotationAdapter, name=EasyQuotationAdapter.name)
    return True
