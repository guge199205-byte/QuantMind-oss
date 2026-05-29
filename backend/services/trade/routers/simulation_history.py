import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.trade.deps import AuthContext, get_auth_context, get_db
from backend.services.trade.simulation.schemas.trade import (
    SimTradeResponse,
    SimTradeStatsResponse,
)
from backend.services.trade.simulation.services.trade_service import SimTradeService

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_user_id(raw_user_id: str) -> str:
    """获取用户ID (字符串类型，兼容 'admin' 等非数字ID)"""
    if not raw_user_id:
        raise HTTPException(status_code=400, detail="Invalid user_id in token")
    return raw_user_id


@router.get("/trades", response_model=list[SimTradeResponse])
async def list_trades(
    portfolio_id: int | None = Query(default=None),
    symbol: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    user_id = _require_user_id(auth.user_id)
    service = SimTradeService(db)
    return await service.list_trades(
        auth.tenant_id,
        user_id,
        portfolio_id=portfolio_id,
        symbol=symbol,
        limit=limit,
        offset=offset,
    )


@router.get("/trades/{trade_id}", response_model=SimTradeResponse)
async def get_trade(
    trade_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    user_id = _require_user_id(auth.user_id)
    service = SimTradeService(db)
    trade = await service.get_trade(auth.tenant_id, user_id, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Simulation trade not found")
    return trade


@router.get("/trades/stats/summary", response_model=SimTradeStatsResponse)
async def get_trade_stats(
    portfolio_id: int | None = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    user_id = _require_user_id(auth.user_id)
    service = SimTradeService(db)
    stats = await service.get_stats(auth.tenant_id, user_id, portfolio_id=portfolio_id)
    logger.info(
        "simulation trade stats ready: tenant_id=%s user_id=%s portfolio_id=%s total_trades=%s daily_points=%s",
        auth.tenant_id,
        user_id,
        portfolio_id,
        stats.get("total_trades", 0),
        len(stats.get("daily_counts", []) or []),
    )
    return SimTradeStatsResponse(**stats)
