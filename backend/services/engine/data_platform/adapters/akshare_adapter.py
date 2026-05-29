"""
akshare adapter — 多市场综合数据（A/HK/US）

akshare 接口非常丰富，本 adapter 暴露：
  daily_kline, financial_report, dividend, sector, share_change,
  research_report, announcement, options_chain, futures_kline
覆盖市场：A / HK / US
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
    import akshare as ak  # type: ignore
    _AK_AVAILABLE = True
except ImportError:  # pragma: no cover
    ak = None  # type: ignore
    _AK_AVAILABLE = False


def _ak_symbol_a(symbol: str) -> str:
    """600519.SH -> sh600519; 000001.SZ -> sz000001"""
    s = symbol.strip().upper()
    if "." in s:
        code, ex = s.split(".", 1)
        return f"{ex.lower()}{code}"
    return s.lower()


def _ak_pure_code(symbol: str) -> str:
    s = symbol.strip().upper()
    return s.split(".", 1)[0]


class AkshareAdapter(OfflineDataSourceAdapter):
    name = "akshare"
    markets = ["A", "HK", "US"]
    fields = {
        "daily_kline",
        "financial_report",
        "dividend",
        "sector",
        "share_change",
        "research_report",
        "announcement",
        "options_chain",
        "futures_kline",
        "f10",
        "margin_trading",
        "block_trade",
        "shareholder_count",
        "share_unlock",
        "institutional_holdings",
        "stock_screening",
        "sec_filing",
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
        if ak is None:
            raise DataUnavailable("akshare not installed")
        adj = {"qfq": "qfq", "hfq": "hfq", "none": ""}.get(adjust, "qfq")

        # 主力接口: stock_zh_a_hist (东方财富源，Docker 内易失败)
        raw = None
        try:
            raw = ak.stock_zh_a_hist(
                symbol=_ak_pure_code(symbol),
                period="daily",
                start_date=start.strftime("%Y%m%d") if start else "20000101",
                end_date=end.strftime("%Y%m%d") if end else "20991231",
                adjust=adj,
            )
        except Exception as exc:
            logger.debug("stock_zh_a_hist failed for %s, trying fallback: %s", symbol, exc)

        # 备用接口: stock_zh_a_daily (新浪源，Docker 内稳定)
        if raw is None or raw.empty:
            try:
                prefix = _ak_symbol_a(symbol)
                raw = ak.stock_zh_a_daily(symbol=prefix, adjust=adj)
                if raw is not None and not raw.empty:
                    # stock_zh_a_daily 列名不同，统一重命名
                    rename_daily = {
                        "date": "trade_date", "open": "open", "close": "close",
                        "high": "high", "low": "low", "volume": "volume", "amount": "amount",
                    }
                    raw = raw.rename(columns=rename_daily)
                    if "trade_date" in raw.columns:
                        raw["trade_date"] = pd.to_datetime(raw["trade_date"])
                        if start:
                            raw = raw[raw["trade_date"] >= pd.Timestamp(start)]
                        if end:
                            raw = raw[raw["trade_date"] <= pd.Timestamp(end)]
            except Exception as exc:
                logger.debug("stock_zh_a_daily also failed for %s: %s", symbol, exc)

        if raw is None or raw.empty:
            raise DataUnavailable(f"akshare empty for {symbol}")

        # 统一列名（stock_zh_a_hist 的中文列名）
        rename = {
            "日期": "trade_date", "开盘": "open", "收盘": "close", "最高": "high",
            "最低": "low", "成交量": "volume", "成交额": "amount",
        }
        df = raw.rename(columns=rename).copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        df["symbol"] = symbol.upper()
        for c in ("open", "high", "low", "close", "volume", "amount"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["adj_factor"] = 1.0
        df["source"] = self.name
        return df[[
            "symbol", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "adj_factor", "source",
        ]]

    def fetch_meta(self, market: str) -> pd.DataFrame:
        if ak is None:
            raise DataUnavailable("akshare not installed")
        m = market.upper()
        try:
            if m == "A":
                raw = ak.stock_info_a_code_name()
            elif m == "HK":
                raw = ak.stock_hk_spot_em()
            elif m == "US":
                raw = ak.stock_us_spot_em()
            else:
                raise InvalidFieldRequest(f"akshare 不支持 market={market}")
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailable(f"akshare meta error: {exc}") from exc
        if raw is None or raw.empty:
            raise DataUnavailable(f"akshare meta empty for {market}")
        df = raw.rename(columns={
            "code": "code", "name": "name", "代码": "code", "名称": "name",
        }).copy()
        df["code"] = df["code"].astype(str)
        if m == "A":
            df["code"] = df["code"].str.zfill(6)
            df["exchange"] = df["code"].apply(_guess_a_exchange)
            df["symbol"] = df["code"] + "." + df["exchange"]
        else:
            df["exchange"] = m
            df["symbol"] = df["code"] + "." + m
        df["market"] = m
        df["list_date"] = None
        df["delist_date"] = None
        df["is_active"] = True
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
        if ak is None:
            raise DataUnavailable("akshare not installed")
        code = _ak_pure_code(symbol)

        if field == "financial_report":
            try:
                raw = ak.stock_financial_report_sina(stock=code, symbol="资产负债表")
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare financial_report empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare financial_report error: {exc}") from exc

        elif field == "dividend":
            try:
                raw = ak.stock_history_dividend_detail(symbol=code, indicator="分红")
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare dividend empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare dividend error: {exc}") from exc

        elif field == "sector":
            try:
                # 获取个股所属行业板块
                raw = ak.stock_board_industry_cons_em(symbol="白酒")
                # 用 stock_individual_info_em 获取行业
                info = ak.stock_individual_info_em(symbol=code)
                if info is None or info.empty:
                    raise DataUnavailable(f"akshare sector empty for {symbol}")
                df = info.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare sector error: {exc}") from exc

        elif field == "f10":
            try:
                raw = ak.stock_individual_info_em(symbol=code)
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare f10 empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare f10 error: {exc}") from exc

        elif field == "margin_trading":
            try:
                raw = ak.stock_margin_detail_szse(date=start.strftime("%Y%m%d") if start else "")
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare margin_trading empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare margin_trading error: {exc}") from exc

        elif field == "block_trade":
            try:
                raw = ak.stock_dzjy_mrmx(symbol=code, start_date=start.strftime("%Y%m%d") if start else "", end_date=end.strftime("%Y%m%d") if end else "")
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare block_trade empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare block_trade error: {exc}") from exc

        elif field == "shareholder_count":
            try:
                raw = ak.stock_zh_a_gdhs_detail_em(symbol=code)
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare shareholder_count empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare shareholder_count error: {exc}") from exc

        elif field == "share_unlock":
            try:
                raw = ak.stock_restricted_release_queue_sina(symbol=code)
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare share_unlock empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare share_unlock error: {exc}") from exc

        elif field == "institutional_holdings":
            try:
                raw = ak.stock_institute_hold_detail(stock=code)
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare institutional_holdings empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare institutional_holdings error: {exc}") from exc

        elif field == "stock_screening":
            try:
                raw = ak.stock_a_indicator_lg(symbol=code)
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare stock_screening empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare stock_screening error: {exc}") from exc

        elif field == "news":
            try:
                raw = ak.stock_news_em(symbol=code)
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare news empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare news error: {exc}") from exc

        elif field == "research_report":
            try:
                raw = ak.stock_research_report_em(symbol=code)
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare research_report empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare research_report error: {exc}") from exc

        elif field == "announcement":
            try:
                raw = ak.stock_notice_report(symbol=code)
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare announcement empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare announcement error: {exc}") from exc

        elif field == "options_chain":
            try:
                raw = ak.option_current_em()
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare options_chain empty")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare options_chain error: {exc}") from exc

        elif field == "futures_kline":
            try:
                raw = ak.futures_main_sina(symbol=code, start_date=start.strftime("%Y%m%d") if start else "", end_date=end.strftime("%Y%m%d") if end else "")
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare futures_kline empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare futures_kline error: {exc}") from exc

        elif field == "share_change":
            try:
                raw = ak.stock_zh_a_gdhs_detail_em(symbol=code)
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare share_change empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare share_change error: {exc}") from exc

        elif field == "sec_filing":
            try:
                raw = ak.stock_notice_report(symbol=code)
                if raw is None or raw.empty:
                    raise DataUnavailable(f"akshare sec_filing empty for {symbol}")
                df = raw.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"akshare sec_filing error: {exc}") from exc

        raise InvalidFieldRequest(f"akshare: field={field} not implemented")


def _guess_a_exchange(code: str) -> str:
    if code.startswith(("60", "68", "9", "11", "5")):
        return "SH"
    if code.startswith(("00", "30", "2")):
        return "SZ"
    if code.startswith(("4", "8")):
        return "BJ"
    return "SH"


def register() -> bool:
    if not _AK_AVAILABLE:
        logger.info("akshare 未安装，跳过 AkshareAdapter 注册")
        return False
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(AkshareAdapter, name=AkshareAdapter.name)
    return True
