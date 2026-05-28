"""
行情数据路由
提供实时行情、历史 K 线、搜索、市场概览等接口
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/market", tags=["Market"])

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


@router.get("/quote")
async def get_quote(
    symbol: str = Query(..., description="股票代码"),
    provider: str = Query("auto", description="数据源: auto/akshare/eastmoney"),
):
    """获取实时行情 (auto 模式: eastmoney 优先，失败回退 akshare)"""
    try:
        if provider == "akshare":
            data = _get_ak().get_realtime_quote(symbol)
        elif provider == "eastmoney":
            data = _get_em().get_realtime_quote(symbol)
        else:
            # auto: eastmoney 更轻量可靠，优先使用
            try:
                data = _get_em().get_realtime_quote(symbol)
                if not data:
                    raise ValueError("empty")
            except Exception:
                data = _get_ak().get_realtime_quote(symbol)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical")
async def get_historical(
    symbol: str = Query(..., description="股票代码"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    period: str = Query("daily", description="周期: daily/weekly/monthly"),
    adjust: str = Query("qfq", description="复权: qfq/hfq/none"),
    days: int = Query(365, description="天数（未指定 start_date 时使用）"),
    provider: str = Query("auto", description="数据源: auto/akshare/eastmoney"),
):
    """获取历史行情 (auto 模式: akshare 优先，失败回退 eastmoney)"""
    from datetime import datetime, timedelta

    if start_date is None:
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        if provider == "eastmoney":
            df = _get_em().get_historical(symbol, start_date, end_date, period, adjust)
        elif provider == "akshare":
            df = _get_ak().get_historical(symbol, start_date, end_date, period, adjust, days=days)
        else:
            # auto: try akshare first, fallback to eastmoney
            try:
                df = _get_ak().get_historical(symbol, start_date, end_date, period, adjust, days=days)
                if df.empty:
                    raise ValueError("empty")
            except Exception:
                df = _get_em().get_historical(symbol, start_date, end_date, period, adjust)
        return {
            "success": True,
            "data": df.to_dict("records"),
            "count": len(df),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search(
    keyword: str = Query(..., description="搜索关键词"),
    limit: int = Query(20, description="返回数量"),
    provider: str = Query("auto", description="数据源: auto/akshare/eastmoney"),
):
    """搜索股票"""
    try:
        if provider == "akshare":
            try:
                results = _get_ak().search(keyword, limit)
            except Exception:
                results = _get_em().search(keyword, limit)
        else:
            results = _get_em().search(keyword, limit)
        return {"success": True, "data": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview")
async def get_overview():
    """获取市场概览"""
    try:
        try:
            data = _get_ak().get_market_overview()
        except Exception:
            # Fallback: 用东方财富接口
            data = {"message": "akshare unavailable, use /indices for index data"}
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indices")
async def get_indices():
    """获取主要指数实时行情"""
    try:
        data = _get_ak().get_index_realtime()
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sectors")
async def get_sectors(limit: int = Query(10, description="返回数量")):
    """获取热门板块"""
    try:
        data = _get_ak().get_hot_sectors(limit)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fund-flow")
async def get_fund_flow(
    symbol: str = Query(..., description="股票代码"),
    limit: int = Query(60, description="天数"),
):
    """获取资金流向（东方财富）"""
    try:
        df = _get_em().get_fund_flow(symbol, limit)
        return {"success": True, "data": df.to_dict("records"), "count": len(df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
