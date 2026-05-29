"""
qstock adapter — 量化行情聚合（覆盖 A 股实时/资金流/新闻/热点）

支持字段：realtime_quote, money_flow, hot_signal, news, sector, daily_kline
覆盖市场：A
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
    import qstock as qs  # type: ignore
    _QS_AVAILABLE = True
except Exception as _qs_exc:  # qstock 顶层 import 会联网，可能 ConnectionError
    qs = None  # type: ignore
    _QS_AVAILABLE = False
    logger.warning("qstock import failed (%s); QstockAdapter 将不可用", _qs_exc)


def _to_qs_code(symbol: str) -> str:
    s = symbol.strip().upper()
    if "." in s:
        return s.split(".", 1)[0]
    return s


class QstockAdapter(OfflineDataSourceAdapter):
    name = "qstock"
    markets = ["A"]
    fields = {
        "daily_kline",
        "realtime_quote",
        "money_flow",
        "hot_signal",
        "news",
        "sector",
    }

    def fetch_daily(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        if qs is None:
            raise DataUnavailable("qstock not installed")
        try:
            raw = qs.get_data(
                _to_qs_code(symbol),
                start=start.strftime("%Y%m%d") if start else None,
                end=end.strftime("%Y%m%d") if end else None,
                freq="d",
                fqt=1 if adjust == "qfq" else (2 if adjust == "hfq" else 0),
            )
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"qstock get_data error: {exc}") from exc
        if raw is None or len(raw) == 0:
            raise DataUnavailable(f"qstock empty for {symbol}")

        df = raw.reset_index() if "date" not in raw.columns else raw.copy()
        rename = {
            "date": "trade_date", "open": "open", "close": "close",
            "high": "high", "low": "low", "volume": "volume", "turnover": "amount",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        if "trade_date" not in df.columns:
            for col in df.columns:
                if "date" in str(col).lower():
                    df = df.rename(columns={col: "trade_date"})
                    break
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        df["symbol"] = symbol.upper()
        for c in ("open", "high", "low", "close", "volume", "amount"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            else:
                df[c] = pd.NA
        df["adj_factor"] = 1.0
        df["source"] = self.name
        return df[[
            "symbol", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "adj_factor", "source",
        ]]

    def fetch_meta(self, market: str) -> pd.DataFrame:
        if qs is None:
            raise DataUnavailable("qstock not installed")
        try:
            raw = qs.realtime_data()
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"qstock realtime_data error: {exc}") from exc
        if raw is None or raw.empty:
            raise DataUnavailable("qstock realtime_data empty")
        df = raw.rename(columns={"代码": "code", "名称": "name"}).copy()
        df["code"] = df["code"].astype(str).str.zfill(6)
        df["exchange"] = df["code"].apply(_guess_exchange)
        df["symbol"] = df["code"] + "." + df["exchange"]
        df["market"] = "A"
        df["is_active"] = True
        df["list_date"] = None
        df["delist_date"] = None
        df["source"] = self.name
        return df[[
            "symbol", "code", "exchange", "name", "market",
            "list_date", "delist_date", "is_active", "source",
        ]]

    def fetch_realtime(self, symbol: str) -> Optional[dict]:
        if qs is None:
            raise DataUnavailable("qstock not installed")
        try:
            df = qs.realtime_data(code=_to_qs_code(symbol))
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"qstock realtime error: {exc}") from exc
        if df is None or df.empty:
            raise DataUnavailable(f"qstock realtime empty for {symbol}")
        r = df.iloc[0].to_dict()
        return {
            "symbol": symbol.upper(),
            "last": r.get("最新") or r.get("最新价"),
            "open": r.get("今开"),
            "high": r.get("最高"),
            "low": r.get("最低"),
            "pre_close": r.get("昨收"),
            "volume": r.get("成交量"),
            "amount": r.get("成交额"),
            "source": self.name,
        }

    def fetch_field(
        self,
        field: str,
        symbol: str,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
        **kwargs,
    ) -> pd.DataFrame:
        if field == "money_flow":
            return self._fetch_money_flow(symbol)
        if field == "hot_signal":
            return self._fetch_hot()
        if field == "news":
            return self._fetch_news(symbol)
        if field == "sector":
            return self._fetch_sector()
        raise InvalidFieldRequest(f"qstock: field={field} not implemented")

    def _fetch_money_flow(self, symbol: str) -> pd.DataFrame:
        raw = qs.stock_money(_to_qs_code(symbol))
        if raw is None or raw.empty:
            raise DataUnavailable(f"qstock money_flow empty for {symbol}")
        raw = raw.copy()
        raw["symbol"] = symbol.upper()
        raw["source"] = self.name
        return raw

    def _fetch_hot(self) -> pd.DataFrame:
        raw = qs.hot_data()
        if raw is None or raw.empty:
            raise DataUnavailable("qstock hot empty")
        raw = raw.copy()
        raw["source"] = self.name
        return raw

    def _fetch_news(self, symbol: str) -> pd.DataFrame:
        raw = qs.news_data()
        if raw is None or raw.empty:
            raise DataUnavailable("qstock news empty")
        raw = raw.copy()
        raw["source"] = self.name
        return raw

    def _fetch_sector(self) -> pd.DataFrame:
        raw = qs.realtime_data(market="行业板块")
        if raw is None or raw.empty:
            raise DataUnavailable("qstock sector empty")
        raw = raw.copy()
        raw["source"] = self.name
        return raw


def _guess_exchange(code: str) -> str:
    if code.startswith(("60", "68", "9")):
        return "SH"
    if code.startswith(("00", "30", "2")):
        return "SZ"
    if code.startswith(("8", "4")):
        return "BJ"
    return "SH"


def register() -> bool:
    if not _QS_AVAILABLE:
        logger.info("qstock 未安装，跳过 QstockAdapter 注册")
        return False
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(QstockAdapter, name=QstockAdapter.name)
    return True
