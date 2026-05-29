"""
Trade API Routes
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.trade.deps import AuthContext, get_auth_context, get_db, get_redis
from backend.services.trade.models.order import TradingMode
from backend.services.trade.redis_client import RedisClient
from backend.services.trade.schemas.trade import TradeListQuery, TradeResponse
from backend.services.trade.services.trade_service import TradeService

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_user_id(raw_user_id: str) -> str:
    """获取用户ID (字符串类型，兼容 'admin' 等非数字ID)"""
    if not raw_user_id:
        raise HTTPException(status_code=400, detail="Invalid user_id in token")
    return raw_user_id


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(
    trade_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Get trade by ID"""
    user_id = _require_user_id(auth.user_id)
    trade_service = TradeService(db, redis)
    trade = await trade_service.get_trade(trade_id, tenant_id=auth.tenant_id, user_id=user_id)

    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Trade {trade_id} not found")

    return trade


@router.get("/", response_model=list[TradeResponse])
async def list_trades(
    portfolio_id: int = None,
    order_id: UUID = None,
    symbol: str = None,
    trading_mode: str | None = None,
    limit: int = 50,
    offset: int = 0,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """List trades with filters"""
    user_id = _require_user_id(auth.user_id)
    normalized_trading_mode = None
    if trading_mode is not None:
        try:
            normalized_trading_mode = TradingMode(str(trading_mode).upper())
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid trading_mode: {trading_mode}",
            ) from exc

    query = TradeListQuery(
        tenant_id=auth.tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        order_id=order_id,
        symbol=symbol,
        trading_mode=normalized_trading_mode,
        limit=limit,
        offset=offset,
    )

    trade_service = TradeService(db, redis)
    trades = await trade_service.list_trades(query)

    return trades


@router.get("/order/{order_id}", response_model=list[TradeResponse])
async def get_trades_by_order(
    order_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Get all trades for a specific order"""
    user_id = _require_user_id(auth.user_id)
    trade_service = TradeService(db, redis)
    trades = await trade_service.get_trades_by_order(auth.tenant_id, user_id, order_id)

    return trades


@router.get("/stats/summary")
async def get_trade_statistics(
    portfolio_id: int = None,
    trading_mode: str | None = None,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Get trade statistics"""
    user_id = _require_user_id(auth.user_id)
    
    normalized_trading_mode = None
    if trading_mode is not None:
        try:
            normalized_trading_mode = TradingMode(str(trading_mode).upper())
        except ValueError:
            # Silently ignore or raise 422 if strictness is preferred
            pass

    trade_service = TradeService(db, redis)
    stats = await trade_service.get_trade_statistics(auth.tenant_id, user_id, portfolio_id, normalized_trading_mode)
    logger.info(
        "trade stats ready: tenant_id=%s user_id=%s portfolio_id=%s total_trades=%s daily_points=%s",
        auth.tenant_id,
        user_id,
        portfolio_id,
        stats.get("total_trades", 0),
        len(stats.get("daily_counts", []) or []),
    )

    return stats
