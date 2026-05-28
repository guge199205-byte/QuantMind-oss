"""
跨市场 K 线 API
==================

GET /api/v1/market/kline?symbol=600519.SH&market=A&period=daily&start=2024-01-01&end=2024-12-31
GET /api/v1/market/kline/{symbol}?market=A&days=120

返回：
{
  "success": true,
  "data": {
    "market": "A",
    "symbol": "600519.SH",
    "period": "daily",
    "source_used": "baostock",
    "items": [{"date":"YYYY-MM-DD","open":...,"high":...,"low":...,"close":...,"volume":..., "amount":...}],
    "fallbacks_tried": ["..."],
    "cleaning_report": {...}
  }
}

策略：
1. 优先走 A 股 stock_daily_latest（命中即返回，时延最低）
2. 否则调用 FieldAggregator.fetch(market, field='daily_kline', symbol=symbol)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.services.api.user_app.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/market", tags=["Market"])


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail=f"invalid date: {s}")


async def _try_stock_daily_latest(symbol: str, start: Optional[date], end: Optional[date], days: int):
    """A 股快路径：从 stock_daily_latest 直接拉。"""
    try:
        from sqlalchemy import text
        from backend.shared.database_pool import get_session
    except Exception:
        return None
    try:
        from backend.services.api.routers.research_service import _to_nominal_price  # type: ignore
    except Exception:
        _to_nominal_price = lambda v, _f: float(v) if v is not None else None  # noqa: E731

    async with get_session(read_only=True) as session:
        if start and end:
            res = await session.execute(
                text(
                    "SELECT trade_date, open, high, low, close, volume, adj_factor "
                    "FROM stock_daily_latest "
                    "WHERE symbol = :s AND trade_date BETWEEN :a AND :b "
                    "ORDER BY trade_date ASC"
                ),
                {"s": symbol, "a": start, "b": end},
            )
        else:
            res = await session.execute(
                text(
                    "SELECT trade_date, open, high, low, close, volume, adj_factor "
                    "FROM stock_daily_latest "
                    "WHERE symbol = :s ORDER BY trade_date DESC LIMIT :l"
                ),
                {"s": symbol, "l": days},
            )
        rows = list(res)
        if not rows:
            return None
        items = []
        for r in rows:
            adj = r[6]
            items.append({
                "date": str(r[0]),
                "open": _to_nominal_price(r[1], adj),
                "high": _to_nominal_price(r[2], adj),
                "low": _to_nominal_price(r[3], adj),
                "close": _to_nominal_price(r[4], adj),
                "volume": float(r[5]) if r[5] is not None else 0.0,
            })
        if not (start and end):
            items.reverse()
        return items


_AGG_CACHE = None


def _get_aggregator():
    global _AGG_CACHE
    if _AGG_CACHE is None:
        from backend.services.engine.data_platform.adapters import register_all
        from backend.services.engine.data_platform.aggregator import (
            FieldAggregator, FieldRoutingTable,
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


def _safe_float(v, default=0.0):
    """Convert a value to float, handling pd.NA/None/NaN."""
    if v is None:
        return default
    try:
        import math
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return default
    except (TypeError, ValueError):
        pass
    try:
        import pandas as pd
        if pd.isna(v):
            return default
    except (TypeError, ValueError):
        pass
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _direct_yahoo_fetch(symbol: str, start: Optional[date], end: Optional[date]):
    """HK/US 快路径：直接调用 yahoo_finance adapter，跳过 aggregator 管线。"""
    from backend.services.engine.data_platform.registry import get_registry
    reg = get_registry()
    adapter = reg.get("yahoo_finance")
    if adapter is None:
        return None
    df = adapter.fetch_daily(symbol, start=start, end=end)
    if df is None or len(df) == 0:
        return None
    items: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        items.append({
            "date": str(r.get("trade_date")),
            "open": _safe_float(r.get("open")),
            "high": _safe_float(r.get("high")),
            "low": _safe_float(r.get("low")),
            "close": _safe_float(r.get("close")),
            "volume": _safe_float(r.get("volume")),
            "amount": _safe_float(r.get("amount"), default=None),
        })
    return {
        "items": items,
        "source_used": "yahoo_finance",
        "fallbacks_tried": [],
        "cleaning_report": {},
    }


def _aggregator_fetch(market: str, symbol: str, start: Optional[date], end: Optional[date]):
    """通过 FieldAggregator 调多源拉日 K。"""
    agg = _get_aggregator()  # cached; register_all() runs only in main thread
    res = agg.fetch(
        market=market, field="daily_kline", symbol=symbol,
        start=start, end=end,
    )
    df = res.data
    items: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        items.append({
            "date": str(r.get("trade_date")),
            "open": float(r.get("open") or 0),
            "high": float(r.get("high") or 0),
            "low": float(r.get("low") or 0),
            "close": float(r.get("close") or 0),
            "volume": float(r.get("volume") or 0),
            "amount": float(r.get("amount") or 0) if r.get("amount") is not None else None,
        })
    return {
        "items": items,
        "source_used": res.source_used,
        "fallbacks_tried": res.fallbacks_tried,
        "cleaning_report": res.cleaning_report,
    }


@router.get("/kline")
async def get_kline(
    symbol: str = Query(..., description="600519.SH / 00700.HK / AAPL"),
    market: str = Query("A", description="A / HK / US"),
    period: str = Query("daily", description="daily 仅支持 daily"),
    start: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD"),
    days: int = Query(120, ge=5, le=2000),
    current_user: dict = Depends(get_current_user),
):
    if period != "daily":
        raise HTTPException(status_code=400, detail=f"period {period} 暂未支持")

    m = market.upper()
    sym = symbol.upper()
    sd = _parse_date(start)
    ed = _parse_date(end)
    if not (sd and ed):
        ed = ed or date.today()
        sd = sd or (ed - timedelta(days=days * 2))

    # A 股优先走 latest 表
    if m == "A":
        try:
            items = await _try_stock_daily_latest(sym, sd, ed, days)
            if items:
                return {
                    "success": True,
                    "data": {
                        "market": m, "symbol": sym, "period": period,
                        "source_used": "stock_daily_latest",
                        "items": items, "fallbacks_tried": [], "cleaning_report": {},
                    },
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock_daily_latest fast-path failed: %s", exc)

    # HK/US 优先走 yahoo_finance 直连（跳过 aggregator 管线，避免超时）
    if m in ("HK", "US"):
        try:
            import asyncio
            payload = await asyncio.to_thread(_direct_yahoo_fetch, sym, sd, ed)
            if payload is not None:
                return {
                    "success": True,
                    "data": {
                        "market": m, "symbol": sym, "period": period,
                        **payload,
                    },
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("yahoo_finance direct fast-path failed: %s", exc)

    try:
        import asyncio
        payload = await asyncio.to_thread(_aggregator_fetch, m, sym, sd, ed)
    except Exception as exc:
        logger.error("aggregator fetch failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail=f"no data: {exc}")

    return {
        "success": True,
        "data": {
            "market": m, "symbol": sym, "period": period,
            **payload,
        },
    }


@router.get("/kline/{symbol}")
async def get_kline_by_path(
    symbol: str,
    market: str = Query("A"),
    days: int = Query(120, ge=5, le=2000),
    current_user: dict = Depends(get_current_user),
):
    """路径参数风格，方便前端写 /api/v1/market/kline/600519.SH?market=A&days=120"""
    return await get_kline(
        symbol=symbol, market=market, period="daily",
        start=None, end=None, days=days, current_user=current_user,
    )
