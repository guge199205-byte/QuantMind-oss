"""
Yahoo Finance adapter — 港股/美股综合数据

使用 yfinance 库，覆盖 HK/US 市场：
  daily_kline, adj_factor, financial_report, dividend, sector, f10,
  news, options_chain, institutional_holdings, sec_filing
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
    import yfinance as yf  # type: ignore
    _YF_AVAILABLE = True
except ImportError:
    yf = None  # type: ignore
    _YF_AVAILABLE = False


def _yf_symbol(symbol: str) -> str:
    """Convert QuantMind symbol to Yahoo Finance ticker.

    00700.HK -> 0700.HK  (strip one leading zero for HK)
    600519.SH -> 600519.SS (Shanghai)
    000001.SZ -> 000001.SZ (Shenzhen)
    AAPL     -> AAPL      (US unchanged)
    """
    s = symbol.strip().upper()
    if s.endswith(".HK"):
        code = s.split(".")[0].lstrip("0") or "0"
        # HK stocks are typically 4-digit codes
        if len(code) < 4:
            code = code.zfill(4)
        return f"{code}.HK"
    if s.endswith(".SH"):
        return s.replace(".SH", ".SS")  # yfinance uses .SS for Shanghai
    return s


class YahooFinanceAdapter(OfflineDataSourceAdapter):
    name = "yahoo_finance"
    markets = ["A", "HK", "US"]
    fields = {
        "daily_kline",
        "adj_factor",
        "financial_report",
        "dividend",
        "sector",
        "f10",
        "news",
        "options_chain",
        "institutional_holdings",
        "sec_filing",
        "income_statement",
        "cash_flow",
        "major_holders",
        "mutual_fund_holders",
        "recommendations",
        "upgrades_downgrades",
        "earnings_estimate",
        "earnings_dates",
        "earnings_history",
        "analyst_price_targets",
        "revenue_estimate",
        "growth_estimates",
        "sustainability",
        "splits",
        "insider_transactions",
        "calendar",
        "valuation",
    }

    def fetch_daily(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        if yf is None:
            raise DataUnavailable("yfinance not installed")
        ticker = _yf_symbol(symbol)
        try:
            raw = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d") if start else "2000-01-01",
                end=end.strftime("%Y-%m-%d") if end else "2099-12-31",
                auto_adjust=False,
                progress=False,
            )
        except Exception as exc:
            raise DataUnavailable(f"yfinance download failed for {ticker}: {exc}") from exc

        if raw is None or raw.empty:
            raise DataUnavailable(f"yfinance empty for {ticker}")

        df = raw.reset_index().copy()
        # yfinance returns multi-level columns for single ticker sometimes
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        # The date column may be named 'Date', 'index', or the index name
        date_col = None
        for candidate in ("Date", "date", "index", df.columns[0]):
            if candidate in df.columns:
                date_col = candidate
                break
        if date_col is None:
            date_col = df.columns[0]

        rename = {
            date_col: "trade_date", "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume", "Adj Close": "adj_close",
        }
        df = df.rename(columns=rename)
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        df["symbol"] = symbol.upper()

        # Calculate adj_factor from Adj Close / Close
        if "adj_close" in df.columns and "close" in df.columns:
            df["adj_factor"] = (
                pd.to_numeric(df["adj_close"], errors="coerce")
                / pd.to_numeric(df["close"], errors="coerce")
            ).fillna(1.0)
        else:
            df["adj_factor"] = 1.0

        for c in ("open", "high", "low", "close", "volume"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        df["amount"] = pd.NA  # Yahoo doesn't provide amount directly
        df["source"] = self.name
        return df[[
            "symbol", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "adj_factor", "source",
        ]]

    def fetch_meta(self, market: str) -> pd.DataFrame:
        if yf is None:
            raise DataUnavailable("yfinance not installed")
        m = market.upper()
        if m == "HK":
            # Use a known list of major HK stocks
            symbols = [
                ("0700.HK", "腾讯控股"), ("9988.HK", "阿里巴巴"),
                ("0388.HK", "香港交易所"), ("0005.HK", "汇丰控股"),
                ("1299.HK", "友邦保险"), ("2318.HK", "中国平安"),
                ("0941.HK", "中国移动"), ("1398.HK", "工商银行"),
                ("3988.HK", "中国银行"), ("0883.HK", "中国海洋石油"),
            ]
        elif m == "US":
            symbols = [
                ("AAPL", "Apple"), ("MSFT", "Microsoft"),
                ("GOOGL", "Alphabet"), ("AMZN", "Amazon"),
                ("NVDA", "NVIDIA"), ("META", "Meta"),
                ("TSLA", "Tesla"), ("BRK-B", "Berkshire Hathaway"),
                ("JPM", "JPMorgan"), ("V", "Visa"),
            ]
        else:
            raise InvalidFieldRequest(f"yahoo_finance 不支持 market={market}")

        rows = []
        for code, name in symbols:
            rows.append({
                "symbol": code, "code": code.split(".")[0],
                "exchange": m, "name": name, "market": m,
                "list_date": None, "delist_date": None,
                "is_active": True, "source": self.name,
            })
        return pd.DataFrame(rows)

    def fetch_field(
        self,
        field: str,
        symbol: str,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
        **kwargs,
    ) -> pd.DataFrame:
        if yf is None:
            raise DataUnavailable("yfinance not installed")
        ticker = _yf_symbol(symbol)
        try:
            t = yf.Ticker(ticker)
        except Exception as exc:
            raise DataUnavailable(f"yfinance ticker failed for {ticker}: {exc}") from exc

        if field == "dividend":
            try:
                div = t.dividends
                if div is None or div.empty:
                    raise DataUnavailable(f"yfinance no dividend for {ticker}")
                df = div.reset_index()
                df.columns = ["trade_date", "dividend"]
                df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance dividend error: {exc}") from exc

        elif field == "financial_report":
            try:
                bs = t.balance_sheet
                if bs is None or bs.empty:
                    raise DataUnavailable(f"yfinance no balance_sheet for {ticker}")
                df = bs.T.reset_index()
                df = df.rename(columns={"index": "report_date"})
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance financial error: {exc}") from exc

        elif field == "options_chain":
            try:
                opts = t.options
                if not opts:
                    raise DataUnavailable(f"yfinance no options for {ticker}")
                # Get first expiry's chain
                chain = t.option_chain(opts[0])
                calls = chain.calls.copy()
                calls["type"] = "call"
                calls["symbol"] = symbol.upper()
                calls["source"] = self.name
                return calls
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance options error: {exc}") from exc

        elif field == "sector":
            try:
                info = t.info
                if not info:
                    raise DataUnavailable(f"yfinance no info for {ticker}")
                df = pd.DataFrame([{
                    "symbol": symbol.upper(),
                    "sector": info.get("sector", ""),
                    "industry": info.get("industry", ""),
                    "source": self.name,
                }])
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance sector error: {exc}") from exc

        elif field == "f10":
            try:
                info = t.info
                if not info:
                    raise DataUnavailable(f"yfinance no info for {ticker}")
                df = pd.DataFrame([{
                    "symbol": symbol.upper(),
                    "name": info.get("longName", ""),
                    "market_cap": info.get("marketCap"),
                    "pe_ratio": info.get("trailingPE"),
                    "pb_ratio": info.get("priceToBook"),
                    "dividend_yield": info.get("dividendYield"),
                    "52w_high": info.get("fiftyTwoWeekHigh"),
                    "52w_low": info.get("fiftyTwoWeekLow"),
                    "avg_volume": info.get("averageVolume"),
                    "source": self.name,
                }])
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance f10 error: {exc}") from exc

        elif field == "income_statement":
            try:
                data = t.income_stmt
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no income_stmt for {ticker}")
                df = data.T.reset_index().rename(columns={"index": "report_date"})
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance income_stmt error: {exc}") from exc

        elif field == "cash_flow":
            try:
                data = t.cash_flow
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no cash_flow for {ticker}")
                df = data.T.reset_index().rename(columns={"index": "report_date"})
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance cash_flow error: {exc}") from exc

        elif field == "major_holders":
            try:
                data = t.major_holders
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no major_holders for {ticker}")
                df = data.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance major_holders error: {exc}") from exc

        elif field == "mutual_fund_holders":
            try:
                data = t.mutualfund_holders
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no mutual_fund_holders for {ticker}")
                df = data.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance mutual_fund_holders error: {exc}") from exc

        elif field == "recommendations":
            try:
                data = t.recommendations
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no recommendations for {ticker}")
                df = data.reset_index() if hasattr(data, 'reset_index') else pd.DataFrame(data)
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance recommendations error: {exc}") from exc

        elif field == "upgrades_downgrades":
            try:
                data = t.upgrades_downgrades
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no upgrades_downgrades for {ticker}")
                df = data.reset_index() if hasattr(data, 'reset_index') else pd.DataFrame(data)
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance upgrades_downgrades error: {exc}") from exc

        elif field == "earnings_estimate":
            try:
                data = t.earnings_estimate
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no earnings_estimate for {ticker}")
                df = data.reset_index() if hasattr(data, 'reset_index') else pd.DataFrame(data)
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance earnings_estimate error: {exc}") from exc

        elif field == "earnings_dates":
            try:
                data = t.earnings_dates
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no earnings_dates for {ticker}")
                df = data.reset_index() if hasattr(data, 'reset_index') else pd.DataFrame(data)
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance earnings_dates error: {exc}") from exc

        elif field == "earnings_history":
            try:
                data = t.earnings_history
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no earnings_history for {ticker}")
                df = data.reset_index() if hasattr(data, 'reset_index') else pd.DataFrame(data)
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance earnings_history error: {exc}") from exc

        elif field == "analyst_price_targets":
            try:
                data = t.analyst_price_targets
                if not data:
                    raise DataUnavailable(f"yfinance no analyst_price_targets for {ticker}")
                df = pd.DataFrame([data])
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance analyst_price_targets error: {exc}") from exc

        elif field == "revenue_estimate":
            try:
                data = t.revenue_estimate
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no revenue_estimate for {ticker}")
                df = data.reset_index() if hasattr(data, 'reset_index') else pd.DataFrame(data)
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance revenue_estimate error: {exc}") from exc

        elif field == "growth_estimates":
            try:
                data = t.growth_estimates
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no growth_estimates for {ticker}")
                df = data.reset_index() if hasattr(data, 'reset_index') else pd.DataFrame(data)
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance growth_estimates error: {exc}") from exc

        elif field == "sustainability":
            try:
                data = t.sustainability
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no sustainability for {ticker}")
                df = data.T.reset_index().rename(columns={"index": "metric"})
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance sustainability error: {exc}") from exc

        elif field == "splits":
            try:
                data = t.splits
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no splits for {ticker}")
                df = data.reset_index()
                df.columns = ["trade_date", "split_ratio"]
                df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance splits error: {exc}") from exc

        elif field == "insider_transactions":
            try:
                data = t.insider_transactions
                if data is None or data.empty:
                    raise DataUnavailable(f"yfinance no insider_transactions for {ticker}")
                df = data.copy()
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance insider_transactions error: {exc}") from exc

        elif field == "calendar":
            try:
                data = t.calendar
                if not data:
                    raise DataUnavailable(f"yfinance no calendar for {ticker}")
                if isinstance(data, pd.DataFrame):
                    df = data.T.reset_index(drop=True)
                else:
                    df = pd.DataFrame([data])
                df["symbol"] = symbol.upper()
                df["source"] = self.name
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance calendar error: {exc}") from exc

        elif field == "valuation":
            try:
                data = t.info
                if not data:
                    raise DataUnavailable(f"yfinance no info for {ticker}")
                df = pd.DataFrame([{
                    "symbol": symbol.upper(),
                    "market_cap": data.get("marketCap"),
                    "enterprise_value": data.get("enterpriseValue"),
                    "trailing_pe": data.get("trailingPE"),
                    "forward_pe": data.get("forwardPE"),
                    "peg_ratio": data.get("pegRatio"),
                    "price_to_book": data.get("priceToBook"),
                    "price_to_sales": data.get("priceToSalesTrailing12Months"),
                    "ev_to_revenue": data.get("enterpriseToRevenue"),
                    "ev_to_ebitda": data.get("enterpriseToEbitda"),
                    "profit_margin": data.get("profitMargins"),
                    "gross_margin": data.get("grossMargins"),
                    "operating_margin": data.get("operatingMargins"),
                    "roe": data.get("returnOnEquity"),
                    "roa": data.get("returnOnAssets"),
                    "revenue": data.get("totalRevenue"),
                    "net_income": data.get("netIncomeToCommon"),
                    "eps": data.get("trailingEps"),
                    "beta": data.get("beta"),
                    "source": self.name,
                }])
                return df
            except DataUnavailable:
                raise
            except Exception as exc:
                raise DataUnavailable(f"yfinance valuation error: {exc}") from exc

        raise InvalidFieldRequest(f"yahoo_finance: field={field} not implemented")


def register() -> bool:
    if not _YF_AVAILABLE:
        logger.info("yfinance 未安装，跳过 YahooFinanceAdapter 注册")
        return False
    from backend.services.engine.data_platform.registry import get_registry
    get_registry().register(YahooFinanceAdapter, name=YahooFinanceAdapter.name)
    return True
