"""
OpenBB-CN adapter — 封装 openbb-cn 子项目的多 provider 数据源

内部按优先级 fallback: eastmoney (免费) > tushare (需 token) > akshare
覆盖 markets: A, HK, US
覆盖 fields: daily_kline, realtime_quote, financial_report, f10, sector, news
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from backend.services.engine.data_platform.base import (
    DataUnavailable,
    InvalidFieldRequest,
    OfflineDataSourceAdapter,
)

logger = logging.getLogger(__name__)

# openbb-cn 路径
OPENBB_CN_DIR = Path(__file__).resolve().parents[4] / "openbb-cn"

# Provider 可用性标记
_EASTMONEY_OK = False
_TUSHARE_OK = False
_AKSHARE_OK = False

try:
    import requests  # noqa: F401
    _EASTMONEY_OK = True
except ImportError:
    pass

try:
    import tushare  # noqa: F401
    if os.environ.get("TUSHARE_TOKEN"):
        _TUSHARE_OK = True
except ImportError:
    pass

try:
    import akshare  # noqa: F401
    _AKSHARE_OK = True
except ImportError:
    pass


def _ensure_openbb_path():
    """将 openbb-cn 加入 sys.path 以便导入 provider。"""
    p = str(OPENBB_CN_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


def _eastmoney_kline(symbol: str, start: Optional[date], end: Optional[date]) -> pd.DataFrame:
    """通过东方财富 API 获取 A 股日 K 线。"""
    import requests as req

    # symbol -> secid
    s = symbol.strip().upper()
    if s.endswith(".SZ"):
        secid = f"0.{s.split('.')[0]}"
    elif s.endswith(".SH"):
        secid = f"1.{s.split('.')[0]}"
    else:
        code = s.split(".")[0] if "." in s else s
        secid = f"1.{code}" if code.startswith(("6", "688")) else f"0.{code}"

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "2",
        "beg": start.strftime("%Y%m%d") if start else "19900101",
        "end": end.strftime("%Y%m%d") if end else "20501231",
        "lmt": 1000000,
    }
    resp = req.get(url, params=params, timeout=15)
    data = resp.json()
    if not data.get("data") or not data["data"].get("klines"):
        raise DataUnavailable(f"eastmoney kline empty for {symbol}")

    rows = []
    for line in data["data"]["klines"]:
        parts = line.split(",")
        rows.append({
            "trade_date": parts[0],
            "open": float(parts[1]),
            "close": float(parts[2]),
            "high": float(parts[3]),
            "low": float(parts[4]),
            "volume": float(parts[5]),
            "amount": float(parts[6]) if len(parts) > 6 else 0,
        })
    df = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    return df


def _tushare_kline(symbol: str, start: Optional[date], end: Optional[date]) -> pd.DataFrame:
    """通过 tushare 获取 A 股日 K 线。"""
    import tushare as ts

    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise DataUnavailable("TUSHARE_TOKEN not set")
    ts.set_token(token)
    pro = ts.pro_api()

    s = symbol.strip().upper()
    if "." not in s:
        code = s.split(".")[0] if "." in s else s
        if code.startswith(("6", "688")):
            ts_code = f"{code}.SH"
        else:
            ts_code = f"{code}.SZ"
    else:
        ts_code = s

    start_str = start.strftime("%Y%m%d") if start else (datetime.now().replace(year=datetime.now().year - 1)).strftime("%Y%m%d")
    end_str = end.strftime("%Y%m%d") if end else datetime.now().strftime("%Y%m%d")

    df = ts.pro_bar(ts_code=ts_code, start_date=start_str, end_date=end_str, adj="qfq")
    if df is None or df.empty:
        raise DataUnavailable(f"tushare kline empty for {symbol}")

    df = df.rename(columns={"trade_date": "trade_date", "vol": "volume"})
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["amount"] = df.get("amount", pd.NA)
    return df


class OpenBBAdapter(OfflineDataSourceAdapter):
    name = "openbb"
    markets = ["A"]
    fields = {
        "daily_kline",
        "realtime_quote",
        "financial_report",
        "f10",
        "sector",
        "news",
    }

    def fetch_daily(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        # 仅支持 A 股
        s = symbol.strip().upper()
        if s.endswith(".HK") or s.endswith(".US"):
            raise InvalidFieldRequest(f"openbb adapter 仅支持 A 股，不支持 {symbol}")

        # 优先 eastmoney (免费)
        if _EASTMONEY_OK:
            try:
                df = _eastmoney_kline(symbol, start, end)
                df["symbol"] = symbol.upper()
                df["adj_factor"] = 1.0
                df["source"] = self.name
                return df[["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount", "adj_factor", "source"]]
            except Exception as exc:
                logger.warning("openbb eastmoney failed for %s: %s", symbol, exc)

        # fallback: tushare
        if _TUSHARE_OK:
            try:
                df = _tushare_kline(symbol, start, end)
                df["symbol"] = symbol.upper()
                df["adj_factor"] = 1.0
                df["source"] = self.name
                return df[["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount", "adj_factor", "source"]]
            except Exception as exc:
                logger.warning("openbb tushare failed for %s: %s", symbol, exc)

        raise DataUnavailable(f"openbb: 所有 provider 均不可用 (eastmoney={_EASTMONEY_OK}, tushare={_TUSHARE_OK})")

    def fetch_meta(self, market: str) -> pd.DataFrame:
        m = market.upper()
        if m != "A":
            raise InvalidFieldRequest(f"openbb 不支持 market={market}")

        # 尝试 tushare 获取完整股票列表
        if _TUSHARE_OK:
            try:
                import tushare as ts
                ts.set_token(os.environ.get("TUSHARE_TOKEN", ""))
                pro = ts.pro_api()
                df = pro.stock_basic(list_status="L", fields="ts_code,name,area,industry,market,list_date")
                df = df.rename(columns={"ts_code": "symbol"})
                df["code"] = df["symbol"].str.split(".").str[0]
                df["exchange"] = "A"
                df["is_active"] = True
                df["delist_date"] = None
                df["source"] = self.name
                return df
            except Exception as exc:
                logger.warning("openbb tushare meta failed: %s", exc)

        # fallback: 返回空但不报错
        return pd.DataFrame(columns=[
            "symbol", "code", "exchange", "name", "market",
            "list_date", "delist_date", "is_active", "source",
        ])

    def fetch_field(
        self,
        field: str,
        symbol: str,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
        **kwargs,
    ) -> pd.DataFrame:
        if field == "financial_report":
            return self._fetch_financial(symbol)
        elif field == "f10":
            return self._fetch_f10(symbol)
        elif field == "sector":
            return self._fetch_sector(symbol)
        elif field == "news":
            return self._fetch_news(symbol)
        elif field == "realtime_quote":
            return self._fetch_realtime(symbol)
        raise InvalidFieldRequest(f"openbb: field={field} not implemented")

    def _fetch_financial(self, symbol: str) -> pd.DataFrame:
        if _TUSHARE_OK:
            try:
                import tushare as ts
                ts.set_token(os.environ.get("TUSHARE_TOKEN", ""))
                pro = ts.pro_api()
                s = symbol.strip().upper()
                if "." not in s:
                    code = s.split(".")[0] if "." in s else s
                    ts_code = f"{code}.SH" if code.startswith(("6", "688")) else f"{code}.SZ"
                else:
                    ts_code = s
                df = pro.income(ts_code=ts_code)
                if df is not None and not df.empty:
                    df["symbol"] = symbol.upper()
                    df["source"] = self.name
                    return df
            except Exception as exc:
                logger.warning("openbb tushare financial failed: %s", exc)
        raise DataUnavailable(f"openbb: financial_report not available for {symbol}")

    def _fetch_f10(self, symbol: str) -> pd.DataFrame:
        if _EASTMONEY_OK:
            try:
                import requests as req
                s = symbol.strip().upper()
                if s.endswith(".SZ"):
                    secid = f"0.{s.split('.')[0]}"
                elif s.endswith(".SH"):
                    secid = f"1.{s.split('.')[0]}"
                else:
                    code = s.split(".")[0] if "." in s else s
                    secid = f"1.{code}" if code.startswith(("6", "688")) else f"0.{code}"

                url = "https://push2.eastmoney.com/api/qt/stock/get"
                params = {
                    "secid": secid,
                    "fields": "f57,f58,f116,f117,f162,f167,f127,f115",
                    "ut": "fa5fd1943c7b386f172d6893dbbd5d51",
                }
                resp = req.get(url, params=params, timeout=10)
                d = resp.json().get("data", {})
                if d:
                    return pd.DataFrame([{
                        "symbol": symbol.upper(),
                        "name": d.get("f58", ""),
                        "market_cap": d.get("f116", 0),
                        "pe_ratio": d.get("f162", 0) / 100 if d.get("f162") else None,
                        "pb_ratio": d.get("f167", 0) / 100 if d.get("f167") else None,
                        "industry": d.get("f127", ""),
                        "source": self.name,
                    }])
            except Exception as exc:
                logger.warning("openbb eastmoney f10 failed: %s", exc)
        raise DataUnavailable(f"openbb: f10 not available for {symbol}")

    def _fetch_sector(self, symbol: str) -> pd.DataFrame:
        if _EASTMONEY_OK:
            try:
                import requests as req
                s = symbol.strip().upper()
                if s.endswith(".SZ"):
                    secid = f"0.{s.split('.')[0]}"
                elif s.endswith(".SH"):
                    secid = f"1.{s.split('.')[0]}"
                else:
                    code = s.split(".")[0] if "." in s else s
                    secid = f"1.{code}" if code.startswith(("6", "688")) else f"0.{code}"

                url = "https://push2.eastmoney.com/api/qt/stock/get"
                params = {"secid": secid, "fields": "f127,f128", "ut": "fa5fd1943c7b386f172d6893dbbd5d51"}
                resp = req.get(url, params=params, timeout=10)
                d = resp.json().get("data", {})
                if d:
                    return pd.DataFrame([{
                        "symbol": symbol.upper(),
                        "sector": d.get("f127", ""),
                        "industry": d.get("f128", ""),
                        "source": self.name,
                    }])
            except Exception as exc:
                logger.warning("openbb eastmoney sector failed: %s", exc)
        raise DataUnavailable(f"openbb: sector not available for {symbol}")

    def _fetch_news(self, symbol: str) -> pd.DataFrame:
        if _EASTMONEY_OK:
            try:
                import requests as req
                url = "https://np-anotice-eastmoney.com/api/security/ann"
                params = {"sr": "-1", "page_size": "20", "page_index": "1", "ann_type": "SHA,CYB,SZA,SHE,NSE", "client_source": "web"}
                s = symbol.strip().upper()
                if s.endswith(".SZ"):
                    params["stock"] = f"0.{s.split('.')[0]}"
                elif s.endswith(".SH"):
                    params["stock"] = f"1.{s.split('.')[0]}"
                resp = req.get(url, params=params, timeout=10)
                data = resp.json()
                if data.get("data") and data["data"].get("list"):
                    rows = []
                    for item in data["data"]["list"]:
                        rows.append({
                            "symbol": symbol.upper(),
                            "title": item.get("title", ""),
                            "publish_time": item.get("publish_time", ""),
                            "category": item.get("notice_category", ""),
                            "source": self.name,
                        })
                    return pd.DataFrame(rows)
            except Exception as exc:
                logger.warning("openbb eastmoney news failed: %s", exc)
        raise DataUnavailable(f"openbb: news not available for {symbol}")

    def _fetch_realtime(self, symbol: str) -> pd.DataFrame:
        if _EASTMONEY_OK:
            try:
                import requests as req
                s = symbol.strip().upper()
                if s.endswith(".SZ"):
                    secid = f"0.{s.split('.')[0]}"
                elif s.endswith(".SH"):
                    secid = f"1.{s.split('.')[0]}"
                else:
                    code = s.split(".")[0] if "." in s else s
                    secid = f"1.{code}" if code.startswith(("6", "688")) else f"0.{code}"

                url = "https://push2.eastmoney.com/api/qt/stock/get"
                params = {
                    "secid": secid,
                    "fields": "f43,f44,f45,f46,f47,f48,f58,f170",
                    "ut": "fa5fd1943c7b386f172d6893dbbd5d51",
                }
                resp = req.get(url, params=params, timeout=10)
                d = resp.json().get("data", {})
                if d:
                    return pd.DataFrame([{
                        "symbol": symbol.upper(),
                        "name": d.get("f58", ""),
                        "price": d.get("f43", 0) / 100,
                        "open": d.get("f46", 0) / 100,
                        "high": d.get("f44", 0) / 100,
                        "low": d.get("f45", 0) / 100,
                        "volume": d.get("f47", 0),
                        "amount": d.get("f48", 0),
                        "pct_change": d.get("f170", 0) / 100,
                        "source": self.name,
                    }])
            except Exception as exc:
                logger.warning("openbb eastmoney realtime failed: %s", exc)
        raise DataUnavailable(f"openbb: realtime_quote not available for {symbol}")


def register() -> bool:
    if not (_EASTMONEY_OK or _TUSHARE_OK or _AKSHARE_OK):
        logger.info("openbb: 无可用 provider，跳过注册")
        return False
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(OpenBBAdapter, name=OpenBBAdapter.name)
    return True
