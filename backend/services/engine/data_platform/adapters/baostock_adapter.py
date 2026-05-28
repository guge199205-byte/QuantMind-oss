"""
A 股第一批适配器 - baostock
================================

支持字段：daily_kline, adj_factor, financial_report, dividend, margin_trading,
         sector, f10, growth, operation, dupont, forecast, performance_express
覆盖市场：A

baostock 接口同步阻塞、需 login/logout，因此 adapter 内部维护一个全局 session 锁。
"""

from __future__ import annotations

import logging
import threading
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
    import baostock as bs  # type: ignore
    _BS_AVAILABLE = True
except ImportError:  # pragma: no cover
    bs = None  # type: ignore
    _BS_AVAILABLE = False


_BS_LOCK = threading.RLock()
_BS_LOGGED_IN = False


def _ensure_login() -> None:
    """baostock 需要 login 才能查询；保证全局只 login 一次。"""
    global _BS_LOGGED_IN
    if bs is None:
        raise DataUnavailable("baostock not installed")
    with _BS_LOCK:
        if _BS_LOGGED_IN:
            return
        rs = bs.login()
        if rs.error_code != "0":
            raise DataUnavailable(f"baostock login failed: {rs.error_msg}")
        _BS_LOGGED_IN = True


def _to_bs_symbol(symbol: str) -> str:
    """600519.SH -> sh.600519, 000001.SZ -> sz.000001"""
    s = symbol.strip().upper()
    if "." in s:
        code, ex = s.split(".", 1)
        return f"{ex.lower()}.{code}"
    return s.lower()


def _from_bs_symbol(bs_code: str) -> str:
    """sh.600519 -> 600519.SH"""
    s = bs_code.strip()
    if "." in s:
        ex, code = s.split(".", 1)
        return f"{code}.{ex.upper()}"
    return s


class BaostockAdapter(OfflineDataSourceAdapter):
    name = "baostock"
    markets = ["A"]
    fields = {
        "daily_kline",
        "adj_factor",
        "financial_report",
        "dividend",
        "margin_trading",
        "sector",
        "f10",
        "growth",
        "operation",
        "dupont",
        "forecast",
        "performance_express",
    }

    def fetch_daily(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        _ensure_login()
        adjustflag = {"qfq": "2", "hfq": "1", "none": "3"}.get(adjust, "2")
        with _BS_LOCK:
            rs = bs.query_history_k_data_plus(
                _to_bs_symbol(symbol),
                "date,open,high,low,close,volume,amount,adjustflag,turn,pctChg",
                start_date=start.isoformat() if start else "",
                end_date=end.isoformat() if end else "",
                frequency="d",
                adjustflag=adjustflag,
            )
            if rs.error_code != "0":
                raise DataUnavailable(f"baostock query failed: {rs.error_msg}")
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
        if not rows:
            raise DataUnavailable(f"baostock empty for {symbol} {start}~{end}")

        df = pd.DataFrame(rows, columns=rs.fields)
        df["symbol"] = symbol.upper()
        df["trade_date"] = pd.to_datetime(df["date"]).dt.date
        for c in ("open", "high", "low", "close", "volume", "amount", "turn", "pctChg"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["adj_factor"] = 1.0  # baostock 已按 adjustflag 返回复权价
        df["source"] = self.name
        return df[[
            "symbol", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "adj_factor", "source",
        ]]

    def fetch_meta(self, market: str) -> pd.DataFrame:
        if market.upper() != "A":
            raise InvalidFieldRequest(f"baostock 不支持 market={market}")
        _ensure_login()
        with _BS_LOCK:
            rs = bs.query_stock_basic()
            if rs.error_code != "0":
                raise DataUnavailable(f"baostock query_stock_basic failed: {rs.error_msg}")
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
        if not rows:
            raise DataUnavailable("baostock query_stock_basic empty")
        df = pd.DataFrame(rows, columns=rs.fields)
        # baostock fields: code,code_name,ipoDate,outDate,type,status
        df["symbol"] = df["code"].map(_from_bs_symbol)
        df["code"] = df["symbol"].str.split(".").str[0]
        df["exchange"] = df["symbol"].str.split(".").str[1]
        df["name"] = df["code_name"]
        df["market"] = "A"
        df["list_date"] = pd.to_datetime(df["ipoDate"], errors="coerce").dt.date
        df["delist_date"] = pd.to_datetime(df["outDate"], errors="coerce").dt.date
        df["is_active"] = df["status"].astype(str) == "1"
        df["source"] = self.name
        return df[[
            "symbol", "code", "exchange", "name", "market",
            "list_date", "delist_date", "is_active", "source",
        ]]

    def fetch_field(
        self,
        field: str,
        symbol: str,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
        **kwargs,
    ) -> pd.DataFrame:
        if field == "adj_factor":
            return self._fetch_adj_factor(symbol, start, end)
        if field == "dividend":
            return self._fetch_dividend(symbol, kwargs.get("year"))
        if field == "financial_report":
            return self._fetch_financial_report(symbol, start, end)
        if field == "sector":
            return self._fetch_sector(symbol)
        if field == "f10":
            return self._fetch_f10(symbol)
        if field == "growth":
            return self._fetch_growth(symbol, start, end)
        if field == "operation":
            return self._fetch_operation(symbol, start, end)
        if field == "dupont":
            return self._fetch_dupont(symbol, start, end)
        if field == "forecast":
            return self._fetch_forecast(symbol, start, end)
        if field == "performance_express":
            return self._fetch_performance_express(symbol, start, end)
        raise InvalidFieldRequest(f"baostock: field={field} not implemented")

    def _fetch_adj_factor(
        self, symbol: str, start: Optional[date], end: Optional[date]
    ) -> pd.DataFrame:
        _ensure_login()
        with _BS_LOCK:
            rs = bs.query_adjust_factor(
                code=_to_bs_symbol(symbol),
                start_date=start.isoformat() if start else "",
                end_date=end.isoformat() if end else "",
            )
            if rs.error_code != "0":
                raise DataUnavailable(f"baostock adj_factor failed: {rs.error_msg}")
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
        if not rows:
            raise DataUnavailable(f"baostock adj_factor empty for {symbol}")
        df = pd.DataFrame(rows, columns=rs.fields)
        df["symbol"] = symbol.upper()
        df["trade_date"] = pd.to_datetime(df["dividOperateDate"]).dt.date
        df["adj_factor"] = pd.to_numeric(df.get("foreAdjustFactor"), errors="coerce")
        df["source"] = self.name
        return df[["symbol", "trade_date", "adj_factor", "source"]].dropna()

    def _fetch_dividend(self, symbol: str, year: Optional[int]) -> pd.DataFrame:
        _ensure_login()
        y = year or date.today().year
        with _BS_LOCK:
            rs = bs.query_dividend_data(
                code=_to_bs_symbol(symbol), year=str(y), yearType="report",
            )
            if rs.error_code != "0":
                raise DataUnavailable(f"baostock dividend failed: {rs.error_msg}")
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
        if not rows:
            raise DataUnavailable(f"baostock dividend empty for {symbol} {y}")
        df = pd.DataFrame(rows, columns=rs.fields)
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df

    def _fetch_financial_report(
        self, symbol: str, start: Optional[date], end: Optional[date]
    ) -> pd.DataFrame:
        _ensure_login()
        bs_code = _to_bs_symbol(symbol)
        year = start.year if start else date.today().year - 1
        quarter = (start.month - 1) // 3 + 1 if start else 4
        all_rows = []
        # 查最近 2 年的财报
        for y in range(year, year + 2):
            for q in range(1, 5):
                if end and y > end.year:
                    break
                with _BS_LOCK:
                    # 利润表
                    rs = bs.query_profit_data(code=bs_code, year=str(y), quarter=q)
                    if rs.error_code == "0":
                        while rs.next():
                            row = rs.get_row_data()
                            row_dict = dict(zip(rs.fields, row))
                            row_dict["_report_type"] = "profit"
                            all_rows.append(row_dict)
                    # 资产负债表
                    rs = bs.query_balance_data(code=bs_code, year=str(y), quarter=q)
                    if rs.error_code == "0":
                        while rs.next():
                            row = rs.get_row_data()
                            row_dict = dict(zip(rs.fields, row))
                            row_dict["_report_type"] = "balance"
                            all_rows.append(row_dict)
                    # 现金流量表
                    rs = bs.query_cash_flow_data(code=bs_code, year=str(y), quarter=q)
                    if rs.error_code == "0":
                        while rs.next():
                            row = rs.get_row_data()
                            row_dict = dict(zip(rs.fields, row))
                            row_dict["_report_type"] = "cash_flow"
                            all_rows.append(row_dict)
        if not all_rows:
            raise DataUnavailable(f"baostock financial_report empty for {symbol}")
        df = pd.DataFrame(all_rows)
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df

    def _fetch_sector(self, symbol: str) -> pd.DataFrame:
        _ensure_login()
        with _BS_LOCK:
            rs = bs.query_stock_industry(code=_to_bs_symbol(symbol))
            if rs.error_code != "0":
                raise DataUnavailable(f"baostock sector failed: {rs.error_msg}")
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
        if not rows:
            raise DataUnavailable(f"baostock sector empty for {symbol}")
        df = pd.DataFrame(rows, columns=rs.fields)
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df

    def _fetch_f10(self, symbol: str) -> pd.DataFrame:
        _ensure_login()
        with _BS_LOCK:
            rs = bs.query_stock_basic(code=_to_bs_symbol(symbol))
            if rs.error_code != "0":
                raise DataUnavailable(f"baostock f10 failed: {rs.error_msg}")
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
        if not rows:
            raise DataUnavailable(f"baostock f10 empty for {symbol}")
        df = pd.DataFrame(rows, columns=rs.fields)
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df

    def _fetch_growth(
        self, symbol: str, start: Optional[date], end: Optional[date]
    ) -> pd.DataFrame:
        _ensure_login()
        bs_code = _to_bs_symbol(symbol)
        year = start.year if start else date.today().year - 1
        all_rows = []
        for y in range(year, year + 2):
            for q in range(1, 5):
                if end and y > end.year:
                    break
                with _BS_LOCK:
                    rs = bs.query_growth_data(code=bs_code, year=str(y), quarter=q)
                    if rs.error_code == "0":
                        while rs.next():
                            all_rows.append(dict(zip(rs.fields, rs.get_row_data())))
        if not all_rows:
            raise DataUnavailable(f"baostock growth empty for {symbol}")
        df = pd.DataFrame(all_rows)
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df

    def _fetch_operation(
        self, symbol: str, start: Optional[date], end: Optional[date]
    ) -> pd.DataFrame:
        _ensure_login()
        bs_code = _to_bs_symbol(symbol)
        year = start.year if start else date.today().year - 1
        all_rows = []
        for y in range(year, year + 2):
            for q in range(1, 5):
                if end and y > end.year:
                    break
                with _BS_LOCK:
                    rs = bs.query_operation_data(code=bs_code, year=str(y), quarter=q)
                    if rs.error_code == "0":
                        while rs.next():
                            all_rows.append(dict(zip(rs.fields, rs.get_row_data())))
        if not all_rows:
            raise DataUnavailable(f"baostock operation empty for {symbol}")
        df = pd.DataFrame(all_rows)
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df

    def _fetch_dupont(
        self, symbol: str, start: Optional[date], end: Optional[date]
    ) -> pd.DataFrame:
        _ensure_login()
        bs_code = _to_bs_symbol(symbol)
        year = start.year if start else date.today().year - 1
        all_rows = []
        for y in range(year, year + 2):
            for q in range(1, 5):
                if end and y > end.year:
                    break
                with _BS_LOCK:
                    rs = bs.query_dupont_data(code=bs_code, year=str(y), quarter=q)
                    if rs.error_code == "0":
                        while rs.next():
                            all_rows.append(dict(zip(rs.fields, rs.get_row_data())))
        if not all_rows:
            raise DataUnavailable(f"baostock dupont empty for {symbol}")
        df = pd.DataFrame(all_rows)
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df

    def _fetch_forecast(
        self, symbol: str, start: Optional[date], end: Optional[date]
    ) -> pd.DataFrame:
        _ensure_login()
        bs_code = _to_bs_symbol(symbol)
        year = start.year if start else date.today().year - 1
        all_rows = []
        for y in range(year, year + 2):
            for q in range(1, 5):
                if end and y > end.year:
                    break
                with _BS_LOCK:
                    rs = bs.query_forecast_report(code=bs_code, year=str(y), quarter=q)
                    if rs.error_code == "0":
                        while rs.next():
                            all_rows.append(dict(zip(rs.fields, rs.get_row_data())))
        if not all_rows:
            raise DataUnavailable(f"baostock forecast empty for {symbol}")
        df = pd.DataFrame(all_rows)
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df

    def _fetch_performance_express(
        self, symbol: str, start: Optional[date], end: Optional[date]
    ) -> pd.DataFrame:
        _ensure_login()
        bs_code = _to_bs_symbol(symbol)
        year = start.year if start else date.today().year - 1
        all_rows = []
        for y in range(year, year + 2):
            for q in range(1, 5):
                if end and y > end.year:
                    break
                with _BS_LOCK:
                    rs = bs.query_performance_express_report(code=bs_code, year=str(y), quarter=q)
                    if rs.error_code == "0":
                        while rs.next():
                            all_rows.append(dict(zip(rs.fields, rs.get_row_data())))
        if not all_rows:
            raise DataUnavailable(f"baostock performance_express empty for {symbol}")
        df = pd.DataFrame(all_rows)
        df["symbol"] = symbol.upper()
        df["source"] = self.name
        return df


def register() -> bool:
    """运行时按需调用；返回是否成功注册。"""
    if not _BS_AVAILABLE:
        logger.info("baostock 未安装，跳过 BaostockAdapter 注册")
        return False
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(BaostockAdapter, name=BaostockAdapter.name)
    return True
