"""
OpenBB SDK 封装服务

使用 OpenBB Platform (v4+) 免费数据源：
- yfinance: 美股、港股行情
- 内置 TA 库: 技术指标计算
- 免费基本面数据

A 股数据优先走 QuantMind DB，不走 OpenBB。
"""

import logging
from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# OpenBB 延迟导入（首次使用时加载）
_obb = None


def _get_obb():
    """延迟加载 OpenBB"""
    global _obb
    if _obb is None:
        try:
            from openbb import obb
            _obb = obb
            logger.info("OpenBB loaded successfully")
        except ImportError as e:
            logger.warning("OpenBB not available: %s", e)
            _obb = False
    return _obb if _obb is not None else None


def is_available() -> bool:
    """检查 OpenBB 是否可用"""
    return _get_obb() is not None


def get_stock_quote(symbol: str, market: str = "US") -> Optional[dict[str, Any]]:
    """获取股票实时报价"""
    obb = _get_obb()
    if not obb:
        return None

    try:
        # 转换符号格式
        obb_symbol = _convert_symbol(symbol, market)
        quote = obb.equity.price.quote(obb_symbol)
        if quote and hasattr(quote, "results") and quote.results:
            r = quote.results[0]
            return {
                "symbol": symbol,
                "price": float(r.last_price or 0),
                "change": float(r.change or 0),
                "change_pct": float(r.change_percent or 0),
                "volume": int(r.volume or 0),
                "market_cap": float(r.market_cap or 0),
                "name": getattr(r, "name", symbol),
            }
    except Exception as e:
        logger.warning("OpenBB quote failed for %s: %s", symbol, e)

    return None


def get_stock_history(
    symbol: str,
    market: str = "US",
    days: int = 120,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> pd.DataFrame:
    """获取股票历史数据"""
    obb = _get_obb()
    if not obb:
        return pd.DataFrame()

    try:
        obb_symbol = _convert_symbol(symbol, market)
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=days)

        data = obb.equity.price.historical(
            obb_symbol,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            provider="yfinance",
        )

        if data and hasattr(data, "results") and data.results:
            records = []
            for r in data.results:
                records.append({
                    "trade_date": r.date,
                    "open": float(r.open or 0),
                    "high": float(r.high or 0),
                    "low": float(r.low or 0),
                    "close": float(r.close or 0),
                    "volume": int(r.volume or 0),
                })
            return pd.DataFrame(records)
    except Exception as e:
        logger.warning("OpenBB history failed for %s: %s", symbol, e)

    return pd.DataFrame()


def get_technical_indicators(
    df: pd.DataFrame,
    indicators: list[str] = None,
) -> dict[str, Any]:
    """计算技术指标

    Args:
        df: 包含 OHLCV 的 DataFrame
        indicators: 指标列表，默认 ["sma", "ema", "rsi", "macd", "bollinger"]

    Returns:
        指标名称 -> 值的字典
    """
    if df.empty or len(df) < 20:
        return {}

    if indicators is None:
        indicators = ["sma", "ema", "rsi", "macd", "bollinger"]

    result = {}

    try:
        import ta

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        if "sma" in indicators:
            result["sma_20"] = ta.trend.sma_indicator(close, window=20).iloc[-1]
            result["sma_60"] = ta.trend.sma_indicator(close, window=60).iloc[-1] if len(df) >= 60 else None

        if "ema" in indicators:
            result["ema_12"] = ta.trend.ema_indicator(close, window=12).iloc[-1]
            result["ema_26"] = ta.trend.ema_indicator(close, window=26).iloc[-1]

        if "rsi" in indicators:
            result["rsi_14"] = ta.momentum.rsi(close, window=14).iloc[-1]

        if "macd" in indicators:
            macd = ta.trend.MACD(close)
            result["macd"] = macd.macd().iloc[-1]
            result["macd_signal"] = macd.macd_signal().iloc[-1]
            result["macd_hist"] = macd.macd_diff().iloc[-1]

        if "bollinger" in indicators:
            bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
            result["bb_upper"] = bb.bollinger_hband().iloc[-1]
            result["bb_middle"] = bb.bollinger_mavg().iloc[-1]
            result["bb_lower"] = bb.bollinger_lband().iloc[-1]

        if "kdj" in indicators:
            stoch = ta.momentum.StochasticOscillator(high, low, close, window=9, smooth_window=3)
            result["k"] = stoch.stoch().iloc[-1]
            result["d"] = stoch.stoch_signal().iloc[-1]
            result["j"] = 3 * result["k"] - 2 * result["d"]

    except Exception as e:
        logger.warning("Technical indicators calculation failed: %s", e)

    return result


def get_fundamentals(symbol: str, market: str = "US") -> Optional[dict[str, Any]]:
    """获取基本面数据"""
    obb = _get_obb()
    if not obb:
        return None

    try:
        obb_symbol = _convert_symbol(symbol, market)
        info = obb.equity.profile(obb_symbol)

        if info and hasattr(info, "results") and info.results:
            r = info.results[0]
            return {
                "symbol": symbol,
                "name": getattr(r, "name", ""),
                "sector": getattr(r, "sector", ""),
                "industry": getattr(r, "industry", ""),
                "market_cap": float(getattr(r, "market_cap", 0) or 0),
                "pe_ratio": float(getattr(r, "pe_ratio", 0) or 0),
                "pb_ratio": float(getattr(r, "pb_ratio", 0) or 0),
                "dividend_yield": float(getattr(r, "dividend_yield", 0) or 0),
                "beta": float(getattr(r, "beta", 0) or 0),
                "52w_high": float(getattr(r, "fifty_two_week_high", 0) or 0),
                "52w_low": float(getattr(r, "fifty_two_week_low", 0) or 0),
                "description": getattr(r, "description", ""),
            }
    except Exception as e:
        logger.warning("OpenBB fundamentals failed for %s: %s", symbol, e)

    return None


def get_news(query: str = "stock market", limit: int = 10) -> list[dict[str, Any]]:
    """获取财经新闻（OpenBB 免费源）"""
    obb = _get_obb()
    if not obb:
        return []

    try:
        news = obb.news.company(query=query, limit=limit)
        if news and hasattr(news, "results"):
            return [
                {
                    "title": getattr(r, "title", ""),
                    "summary": getattr(r, "summary", ""),
                    "url": getattr(r, "url", ""),
                    "source": getattr(r, "source", ""),
                    "date": str(getattr(r, "date", "")),
                }
                for r in news.results[:limit]
            ]
    except Exception as e:
        logger.warning("OpenBB news failed: %s", e)

    return []


def _convert_symbol(symbol: str, market: str) -> str:
    """将 QuantMind 股票符号转换为 OpenBB 格式"""
    if market.upper() == "A":
        # A 股: 600519.SH -> 600519.SS (Yahoo Finance 格式)
        if "." in symbol:
            code, exchange = symbol.split(".")
            if exchange.upper() == "SH":
                return f"{code}.SS"
            elif exchange.upper() == "SZ":
                return f"{code}.SZ"
        return symbol
    elif market.upper() == "HK":
        # 港股: 00700.HK -> 0700.HK
        if "." in symbol:
            code, exchange = symbol.split(".")
            return f"{code.lstrip('0')}.HK" if code != "00000" else "0000.HK"
        return symbol
    else:
        # 美股: 直接使用
        return symbol
