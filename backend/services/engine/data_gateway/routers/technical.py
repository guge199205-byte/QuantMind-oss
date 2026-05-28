"""
技术指标路由
提供 MA/EMA/MACD/RSI/KDJ/BOLL 等技术指标计算
"""

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/technical", tags=["Technical"])

# Provider 单例
_ak = None
_em = None


def _get_ak():
    global _ak
    if _ak is None:
        from backend.services.engine.data_gateway.providers.akshare_provider import AkShareProvider
        _ak = AkShareProvider()
    return _ak


def _get_em():
    global _em
    if _em is None:
        from backend.services.engine.data_gateway.providers.eastmoney_provider import EastMoneyProvider
        _em = EastMoneyProvider()
    return _em


def _get_historical(symbol: str, days: int = 250):
    """获取历史数据用于指标计算，akshare 失败时回退到 eastmoney"""
    import pandas as pd
    from datetime import datetime, timedelta

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        df = _get_ak().get_historical(symbol, start, end)
        if not df.empty:
            return df
    except Exception:
        pass

    return _get_em().get_historical(symbol, start, end)


def _sanitize(values):
    """Replace NaN/inf with None for JSON serialization"""
    import math
    return [None if (v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))) else round(v, 4) for v in values]


def _calc_indicators(df, indicators: list[str]):
    """计算技术指标"""
    if df.empty or len(df) < 5:
        return {}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    result = {}

    try:
        import ta

        if "ma" in indicators:
            for p in [5, 10, 20, 60]:
                if len(df) >= p:
                    result[f"ma{p}"] = _sanitize(ta.trend.sma_indicator(close, window=p).tolist())

        if "ema" in indicators:
            for p in [12, 26]:
                if len(df) >= p:
                    result[f"ema{p}"] = _sanitize(ta.trend.ema_indicator(close, window=p).tolist())

        if "macd" in indicators:
            if len(df) >= 26:
                macd = ta.trend.MACD(close)
                result["macd_line"] = _sanitize(macd.macd().tolist())
                result["macd_signal"] = _sanitize(macd.macd_signal().tolist())
                result["macd_hist"] = _sanitize(macd.macd_diff().tolist())

        if "rsi" in indicators:
            if len(df) >= 14:
                result["rsi14"] = _sanitize(ta.momentum.rsi(close, window=14).tolist())

        if "kdj" in indicators:
            if len(df) >= 9:
                stoch = ta.momentum.StochasticOscillator(high, low, close, window=9, smooth_window=3)
                result["k"] = _sanitize(stoch.stoch().tolist())
                result["d"] = _sanitize(stoch.stoch_signal().tolist())
                k_vals = stoch.stoch().values
                d_vals = stoch.stoch_signal().values
                result["j"] = _sanitize((3 * k_vals - 2 * d_vals).tolist())

        if "boll" in indicators:
            if len(df) >= 20:
                bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
                result["boll_upper"] = _sanitize(bb.bollinger_hband().tolist())
                result["boll_middle"] = _sanitize(bb.bollinger_mavg().tolist())
                result["boll_lower"] = _sanitize(bb.bollinger_lband().tolist())

        if "obv" in indicators:
            if "volume" in df.columns:
                result["obv"] = _sanitize(ta.volume.on_balance_volume(close, df["volume"].astype(float)).tolist())

        if "atr" in indicators:
            if len(df) >= 14:
                result["atr"] = _sanitize(ta.volatility.average_true_range(high, low, close, window=14).tolist())

    except ImportError:
        if "ma" in indicators:
            for p in [5, 10, 20, 60]:
                if len(df) >= p:
                    result[f"ma{p}"] = _sanitize(close.rolling(window=p).mean().tolist())
        if "rsi" in indicators and len(df) >= 14:
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            result["rsi14"] = _sanitize((100 - 100 / (1 + rs)).tolist())

    return result


@router.get("/ma")
async def get_ma(
    symbol: str = Query(..., description="股票代码"),
    periods: str = Query("5,10,20,60", description="MA 周期，逗号分隔"),
):
    """计算移动平均线"""
    try:
        df = _get_historical(symbol)
        result = _calc_indicators(df, ["ma"])
        return {"success": True, "data": result, "dates": df["trade_date"].tolist()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/macd")
async def get_macd(
    symbol: str = Query(..., description="股票代码"),
):
    """计算 MACD"""
    try:
        df = _get_historical(symbol)
        result = _calc_indicators(df, ["macd"])
        return {"success": True, "data": result, "dates": df["trade_date"].tolist()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rsi")
async def get_rsi(
    symbol: str = Query(..., description="股票代码"),
):
    """计算 RSI"""
    try:
        df = _get_historical(symbol)
        result = _calc_indicators(df, ["rsi"])
        return {"success": True, "data": result, "dates": df["trade_date"].tolist()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kdj")
async def get_kdj(
    symbol: str = Query(..., description="股票代码"),
):
    """计算 KDJ"""
    try:
        df = _get_historical(symbol)
        result = _calc_indicators(df, ["kdj"])
        return {"success": True, "data": result, "dates": df["trade_date"].tolist()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/boll")
async def get_boll(
    symbol: str = Query(..., description="股票代码"),
):
    """计算布林带"""
    try:
        df = _get_historical(symbol)
        result = _calc_indicators(df, ["boll"])
        return {"success": True, "data": result, "dates": df["trade_date"].tolist()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
async def get_all_indicators(
    symbol: str = Query(..., description="股票代码"),
):
    """计算所有常用技术指标"""
    try:
        df = _get_historical(symbol)
        result = _calc_indicators(df, ["ma", "ema", "macd", "rsi", "kdj", "boll", "obv", "atr"])
        return {"success": True, "data": result, "dates": df["trade_date"].tolist()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
