"""KLine API endpoints"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db, get_redis
from ...schemas import KLineListResponse, KLineResponse
from ...services import KLineService

router = APIRouter(prefix="/klines", tags=["klines"])


@router.get("/{symbol}", response_model=KLineListResponse)
async def get_klines(
    symbol: str,
    interval: str = Query("1d", description="时间周期 (1m/5m/15m/30m/1h/4h/1d/1w/1M)"),
    start_time: datetime | None = Query(None, description="开始时间"),
    end_time: datetime | None = Query(None, description="结束时间"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    use_cache: bool = Query(True, description="是否使用缓存"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """获取K线数据"""
    service = KLineService(db, redis)
    klines = await service.get_klines(symbol, interval, start_time, end_time, limit, use_cache)

    return KLineListResponse(total=len(klines), klines=klines)


@router.get("/{symbol}/latest", response_model=KLineResponse)
async def get_latest_kline(
    symbol: str,
    interval: str = Query("1d", description="时间周期"),
    db: AsyncSession = Depends(get_db),
):
    """获取最新K线"""
    service = KLineService(db)
    kline = await service.get_latest_kline(symbol, interval)

    if not kline:
        raise HTTPException(
            status_code=404,
            detail=f"No kline found for symbol: {symbol}, interval: {interval}",
        )

    return kline
