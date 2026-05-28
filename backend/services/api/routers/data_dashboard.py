"""
数据看板 API
============

为前端数据看板提供全市场全字段数据访问。
复用 FieldAggregator 路由/聚合能力，暴露以下端点：

GET /api/v1/data-dashboard/fields       — 按市场列出可用字段
GET /api/v1/data-dashboard/field-data   — 获取任意字段数据
GET /api/v1/data-dashboard/realtime     — 实时行情
GET /api/v1/data-dashboard/sectors      — 行业板块
GET /api/v1/data-dashboard/meta         — 股票基本信息
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.services.api.user_app.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/data-dashboard", tags=["DataDashboard"])


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail=f"invalid date: {s}")


_AGG_CACHE = None


def _get_aggregator():
    global _AGG_CACHE
    if _AGG_CACHE is None:
        from backend.services.engine.data_platform.adapters import register_all
        from backend.services.engine.data_platform.aggregator import (
            FieldAggregator,
            FieldRoutingTable,
        )
        from backend.services.engine.data_platform.cleaner import DataCleaner
        from backend.services.engine.data_platform.monitor import get_monitor
        from backend.services.engine.data_platform.registry import get_registry

        register_all()
        _AGG_CACHE = FieldAggregator(
            registry=get_registry(),
            routing=FieldRoutingTable(),
            monitor=get_monitor(),
            cleaner=DataCleaner(),
        )
    return _AGG_CACHE


def _get_routing():
    from backend.services.engine.data_platform.aggregator import FieldRoutingTable
    return FieldRoutingTable()


# ---------------------------------------------------------------------------
# GET /fields — 按市场列出所有可用字段
# ---------------------------------------------------------------------------
@router.get("/fields")
async def list_fields(
    market: str = Query("A", description="A / HK / US"),
    current_user: dict = Depends(get_current_user),
):
    routing = _get_routing()
    fields = routing.list_fields(market.upper())
    result = []
    for f in fields:
        try:
            route = routing.get_route(market.upper(), f)
            result.append({
                "field": f,
                "tier": route.tier,
                "primary": route.primary,
                "fallbacks": route.fallbacks,
                "consensus": route.consensus,
                "cleanup": route.cleanup,
            })
        except Exception:
            result.append({"field": f, "tier": "T1", "primary": "", "fallbacks": []})
    return {
        "success": True,
        "market": market.upper(),
        "fields": result,
        "count": len(result),
    }


# ---------------------------------------------------------------------------
# GET /field-data — 获取任意字段数据（通用）
# ---------------------------------------------------------------------------
@router.get("/field-data")
async def get_field_data(
    market: str = Query(..., description="A / HK / US"),
    field: str = Query(..., description="字段名，如 daily_kline, financial_report, dividend"),
    symbol: str = Query(..., description="股票代码"),
    start: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD"),
    days: int = Query(365, ge=1, le=2000),
    current_user: dict = Depends(get_current_user),
):
    sd = _parse_date(start)
    ed = _parse_date(end)
    if not (sd and ed):
        ed = ed or date.today()
        sd = sd or (ed - timedelta(days=days))

    agg = _get_aggregator()
    try:
        import asyncio
        result = await asyncio.to_thread(
            agg.fetch,
            market=market.upper(),
            field=field,
            symbol=symbol.upper(),
            start=sd,
            end=ed,
        )
    except Exception as exc:
        logger.warning("field-data fetch failed: market=%s field=%s symbol=%s err=%s",
                        market, field, symbol, exc)
        raise HTTPException(status_code=503, detail=f"数据获取失败: {exc}")

    df = result.data
    # 将 DataFrame 转为 records，处理 NaN/NaT
    records = df.replace({float("nan"): None}).to_dict("records")
    # 转换 date/datetime 对象为字符串
    for rec in records:
        for k, v in rec.items():
            if isinstance(v, (date, datetime)):
                rec[k] = v.isoformat()

    return {
        "success": True,
        "market": market.upper(),
        "field": field,
        "symbol": symbol.upper(),
        "source_used": result.source_used,
        "fallbacks_tried": result.fallbacks_tried,
        "count": len(records),
        "columns": list(df.columns),
        "data": records,
    }


# ---------------------------------------------------------------------------
# GET /realtime — 实时行情
# ---------------------------------------------------------------------------
@router.get("/realtime")
async def get_realtime(
    market: str = Query("A", description="A / HK / US"),
    symbol: str = Query(..., description="股票代码"),
    current_user: dict = Depends(get_current_user),
):
    agg = _get_aggregator()
    try:
        import asyncio
        result = await asyncio.to_thread(
            agg.fetch,
            market=market.upper(),
            field="realtime_quote",
            symbol=symbol.upper(),
        )
    except Exception as exc:
        logger.warning("realtime fetch failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"实时行情获取失败: {exc}")

    df = result.data
    if df.empty:
        raise HTTPException(status_code=404, detail="无实时数据")

    row = df.iloc[0].to_dict()
    # 清理 NaN
    quote = {k: (None if _is_nan(v) else v) for k, v in row.items()}
    return {
        "success": True,
        "market": market.upper(),
        "symbol": symbol.upper(),
        "source_used": result.source_used,
        "quote": quote,
    }


def _is_nan(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float):
        import math
        return math.isnan(v) or math.isinf(v)
    return False


# ---------------------------------------------------------------------------
# GET /sectors — 行业板块
# ---------------------------------------------------------------------------
@router.get("/sectors")
async def get_sectors(
    market: str = Query("A", description="A / HK / US"),
    symbol: str = Query("000001.SZ", description="任意一个该市场的股票代码（用于获取行业信息）"),
    current_user: dict = Depends(get_current_user),
):
    agg = _get_aggregator()
    try:
        import asyncio
        result = await asyncio.to_thread(
            agg.fetch,
            market=market.upper(),
            field="sector",
            symbol=symbol.upper(),
        )
    except Exception as exc:
        logger.warning("sector fetch failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"行业数据获取失败: {exc}")

    df = result.data
    records = df.replace({float("nan"): None}).to_dict("records")
    for rec in records:
        for k, v in rec.items():
            if isinstance(v, (date, datetime)):
                rec[k] = v.isoformat()

    return {
        "success": True,
        "market": market.upper(),
        "source_used": result.source_used,
        "count": len(records),
        "data": records,
    }


# ---------------------------------------------------------------------------
# GET /meta — 股票基本信息（F10）
# ---------------------------------------------------------------------------
@router.get("/meta")
async def get_meta(
    market: str = Query("A", description="A / HK / US"),
    symbol: str = Query(..., description="股票代码"),
    current_user: dict = Depends(get_current_user),
):
    agg = _get_aggregator()
    try:
        import asyncio
        result = await asyncio.to_thread(
            agg.fetch,
            market=market.upper(),
            field="f10",
            symbol=symbol.upper(),
        )
    except Exception as exc:
        logger.warning("meta/f10 fetch failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"基本信息获取失败: {exc}")

    df = result.data
    records = df.replace({float("nan"): None}).to_dict("records")
    for rec in records:
        for k, v in rec.items():
            if isinstance(v, (date, datetime)):
                rec[k] = v.isoformat()

    return {
        "success": True,
        "market": market.upper(),
        "symbol": symbol.upper(),
        "source_used": result.source_used,
        "data": records,
    }


# ---------------------------------------------------------------------------
# GET /search — 股票搜索（复用 stocks_index）
# ---------------------------------------------------------------------------
@router.get("/search")
async def search_stocks(
    keyword: str = Query(..., description="搜索关键词"),
    market: Optional[str] = Query(None, description="A / HK / US，不指定则全市场"),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    # 优先使用 stocks_search 的 JSON 索引
    try:
        from backend.services.api.routers.stocks_search import stock_index_store
        results = stock_index_store.search(keyword=keyword, limit=limit)
        # 按 market 过滤
        if market:
            m = market.upper()
            if m == "A":
                results = [r for r in results if r.get("market") in ("SH", "SZ", "BJ")]
            elif m == "HK":
                results = [r for r in results if r.get("market") == "HK"]
            elif m == "US":
                results = [r for r in results if r.get("market") == "US"]
        return {
            "success": True,
            "keyword": keyword,
            "market": market,
            "results": results,
            "count": len(results),
        }
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning("stock index search failed: %s", exc)

    # 回退：从 data_platform 的 fetch_meta 搜索
    try:
        agg = _get_aggregator()
        from backend.services.engine.data_platform.registry import get_registry
        reg = get_registry()
        # 用 baostock(A) / yahoo_finance(HK/US) 的 fetch_meta
        m = (market or "A").upper()
        if m == "A":
            adapter = reg.get("baostock")
        elif m == "HK":
            adapter = reg.get("yahoo_finance")
        else:
            adapter = reg.get("yahoo_finance")

        meta_df = adapter.fetch_meta(m)
        k = keyword.strip().lower()
        mask = (
            meta_df["symbol"].str.lower().str.contains(k, na=False)
            | meta_df["name"].str.lower().str.contains(k, na=False)
        )
        matched = meta_df[mask].head(limit)
        results = []
        for _, r in matched.iterrows():
            results.append({
                "symbol": r.get("symbol", ""),
                "code": r.get("code", ""),
                "name": r.get("name", ""),
                "market": r.get("exchange", m),
            })
        return {
            "success": True,
            "keyword": keyword,
            "market": market,
            "results": results,
            "count": len(results),
        }
    except Exception as exc:
        logger.error("search fallback failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"搜索失败: {exc}")
