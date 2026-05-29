"""
Asset API Routes - 用户资产数据接口
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.user_app.middleware.auth import get_current_user
from backend.shared.database_manager_v2 import get_session

router = APIRouter()


@router.get("/summary")
async def get_asset_summary(
    current_user: dict = Depends(get_current_user),
):
    """
    获取用户资产概览
    """
    user_id = current_user["user_id"]
    tenant_id = current_user["tenant_id"]

    async with get_session(read_only=True) as session:
        from sqlalchemy import text

        result = await session.execute(
            text("""
            SELECT 
                account_id,
                snapshot_date,
                total_asset,
                cash,
                market_value,
                today_pnl_raw,
                total_pnl_raw,
                daily_return_pct,
                total_return_pct,
                month_open_equity,
                initial_equity
            FROM real_account_ledger_daily_snapshots
            WHERE user_id = :user_id AND tenant_id = :tenant_id
            ORDER BY snapshot_date DESC
            LIMIT 1
        """),
            {"user_id": user_id, "tenant_id": tenant_id},
        )

        row = result.first()

        if not row:
            return {
                "code": 200,
                "message": "success",
                "data": None,
            }

        return {
            "code": 200,
            "message": "success",
            "data": {
                "account_id": row.account_id,
                "snapshot_date": str(row.snapshot_date),
                "total_asset": float(row.total_asset) if row.total_asset else 0,
                "cash": float(row.cash) if row.cash else 0,
                "market_value": float(row.market_value) if row.market_value else 0,
                "today_pnl": float(row.today_pnl_raw) if row.today_pnl_raw else 0,
                "total_pnl": float(row.total_pnl_raw) if row.total_pnl_raw else 0,
                "daily_return": float(row.daily_return_pct)
                if row.daily_return_pct
                else 0,
                "total_return": float(row.total_return_pct)
                if row.total_return_pct
                else 0,
                "month_open_equity": float(row.month_open_equity)
                if row.month_open_equity
                else 0,
                "initial_equity": float(row.initial_equity)
                if row.initial_equity
                else 0,
            },
        }


@router.get("/history")
async def get_asset_history(
    days: int = Query(30, ge=1, le=365, description="查询天数"),
    current_user: dict = Depends(get_current_user),
):
    """
    获取用户资产历史数据
    """
    user_id = current_user["user_id"]
    tenant_id = current_user["tenant_id"]

    async with get_session(read_only=True) as session:
        from sqlalchemy import text

        result = await session.execute(
            text("""
            SELECT 
                snapshot_date,
                total_asset,
                cash,
                market_value,
                today_pnl_raw,
                total_pnl_raw,
                daily_return_pct,
                total_return_pct
            FROM real_account_ledger_daily_snapshots
            WHERE user_id = :user_id AND tenant_id = :tenant_id
            ORDER BY snapshot_date DESC
            LIMIT :days
        """),
            {"user_id": user_id, "tenant_id": tenant_id, "days": days},
        )

        rows = result.fetchall()

        history = []
        for row in reversed(rows):
            history.append(
                {
                    "date": str(row.snapshot_date),
                    "total_asset": float(row.total_asset) if row.total_asset else 0,
                    "cash": float(row.cash) if row.cash else 0,
                    "market_value": float(row.market_value) if row.market_value else 0,
                    "today_pnl": float(row.today_pnl_raw) if row.today_pnl_raw else 0,
                    "total_pnl": float(row.total_pnl_raw) if row.total_pnl_raw else 0,
                    "daily_return": float(row.daily_return_pct)
                    if row.daily_return_pct
                    else 0,
                    "total_return": float(row.total_return_pct)
                    if row.total_return_pct
                    else 0,
                }
            )

        return {
            "code": 200,
            "message": "success",
            "data": history,
        }


@router.get("/positions")
async def get_positions(
    current_user: dict = Depends(get_current_user),
):
    """
    获取用户持仓信息
    """
    user_id = current_user["user_id"]
    tenant_id = current_user["tenant_id"]

    async with get_session(read_only=True) as session:
        from sqlalchemy import text

        result = await session.execute(
            text("""
            SELECT 
                p.symbol,
                p.quantity,
                p.available_quantity,
                p.average_cost,
                p.current_price,
                p.market_value,
                p.floating_pnl,
                p.floating_pnl_pct
            FROM positions p
            JOIN portfolios pf ON p.portfolio_id = pf.id
            WHERE pf.user_id = :user_id 
              AND pf.tenant_id = :tenant_id 
              AND pf.is_deleted = false
              AND p.quantity > 0
            ORDER BY p.market_value DESC
        """),
            {"user_id": user_id, "tenant_id": tenant_id},
        )

        rows = result.fetchall()

        positions = []
        for row in rows:
            positions.append(
                {
                    "symbol": row.symbol,
                    "quantity": float(row.quantity) if row.quantity else 0,
                    "available_quantity": float(row.available_quantity)
                    if row.available_quantity
                    else 0,
                    "average_cost": float(row.average_cost) if row.average_cost else 0,
                    "current_price": float(row.current_price)
                    if row.current_price
                    else 0,
                    "market_value": float(row.market_value) if row.market_value else 0,
                    "floating_pnl": float(row.floating_pnl) if row.floating_pnl else 0,
                    "floating_pnl_pct": float(row.floating_pnl_pct)
                    if row.floating_pnl_pct
                    else 0,
                }
            )

        return {
            "code": 200,
            "message": "success",
            "data": positions,
        }
