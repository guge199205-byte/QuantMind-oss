"""Quote API endpoints"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db, get_redis
from ...schemas import QuoteListResponse, QuoteResponse
from ...services import QuoteService

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.get("/{symbol}", response_model=QuoteResponse)
async def get_quote(
    symbol: str,
    source: str | None = Query(None, description="数据源 (ifind/tencent/sina)"),
    use_cache: bool = Query(True, description="是否使用缓存"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """获取实时行情"""
    service = QuoteService(db, redis)
    try:
        quote = await service.get_quote(symbol, source, use_cache)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not quote:
        raise HTTPException(status_code=404, detail=f"Quote not found for symbol: {symbol}")

    return quote


@router.get("/", response_model=QuoteListResponse)
async def list_quotes(
    symbol: str | None = Query(None, description="股票代码"),
    start_time: datetime | None = Query(None, description="开始时间"),
    end_time: datetime | None = Query(None, description="结束时间"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
):
    """查询行情历史"""
    service = QuoteService(db)
    quotes = await service.list_quotes(symbol, start_time, end_time, limit, offset)

    return QuoteListResponse(total=len(quotes), quotes=quotes)


@router.get("/{symbol}/latest", response_model=QuoteResponse)
async def get_latest_quote(symbol: str, db: AsyncSession = Depends(get_db)):
    """获取最新行情"""
    service = QuoteService(db)
    quote = await service.get_latest_quote(symbol)

    if not quote:
        raise HTTPException(status_code=404, detail=f"No quote found for symbol: {symbol}")

    return quote


@router.get("/{symbol}/series")
async def get_quote_series(
    symbol: str,
    seconds: int = Query(3600, description="获取过去多少秒的数据"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """
    获取行情时间窗口序列 (用于计算日内技术指标)
    """
    service = QuoteService(db, redis)
    # 直接调用 RemoteRedisSource 的时序拉取能力
    source = service.data_sources.get("remote_redis")
    if not source:
        raise HTTPException(status_code=500, detail="Remote Redis source not initialized")

    series = await source.fetch_series(symbol, seconds)
    return {"symbol": symbol, "seconds": seconds, "count": len(series), "data": series}
