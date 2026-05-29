"""
Simulation trade service.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.trade.simulation.models.trade import SimTrade


class SimTradeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_trade(self, tenant_id: str, user_id: int, trade_id: UUID) -> SimTrade | None:
        result = await self.db.execute(
            select(SimTrade).where(
                and_(
                    SimTrade.tenant_id == tenant_id,
                    SimTrade.user_id == user_id,
                    SimTrade.trade_id == trade_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_trades(
        self,
        tenant_id: str,
        user_id: int,
        *,
        portfolio_id: int | None = None,
        symbol: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SimTrade]:
        conditions = [SimTrade.tenant_id == tenant_id, SimTrade.user_id == user_id]
        if portfolio_id is not None:
            conditions.append(SimTrade.portfolio_id == portfolio_id)
        if symbol:
            conditions.append(SimTrade.symbol == symbol.upper())

        stmt = (
            select(SimTrade).where(and_(*conditions)).order_by(SimTrade.executed_at.desc()).limit(limit).offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_stats(self, tenant_id: str, user_id: int, portfolio_id: int | None = None) -> dict:
        conditions = [SimTrade.tenant_id == tenant_id, SimTrade.user_id == user_id]
        if portfolio_id is not None:
            conditions.append(SimTrade.portfolio_id == portfolio_id)

        summary_stmt = select(
            func.count(SimTrade.id).label("total_trades"),
            func.coalesce(func.sum(SimTrade.trade_value), 0.0).label("total_value"),
            func.coalesce(func.sum(SimTrade.commission), 0.0).label("total_commission"),
            func.coalesce(func.sum(case((SimTrade.side == "buy", 1), else_=0)), 0).label("buy_trades"),
            func.coalesce(func.sum(case((SimTrade.side == "sell", 1), else_=0)), 0).label("sell_trades"),
        ).where(and_(*conditions))
        summary_row = (await self.db.execute(summary_stmt)).one()

        day_bucket = func.date(SimTrade.executed_at)
        daily_stmt = (
            select(day_bucket.label("trade_day"), func.count(SimTrade.id).label("trade_count"))
            .where(and_(*conditions))
            .group_by(day_bucket)
            .order_by(day_bucket.asc())
        )
        daily_rows = (await self.db.execute(daily_stmt)).all()
        daily_counts = []
        for row in daily_rows:
            trade_day = row.trade_day
            if not trade_day:
                continue
            day_text = trade_day.isoformat()
            daily_counts.append(
                {
                    "timestamp": f"{day_text}T00:00:00Z",
                    "value": int(row.trade_count or 0),
                    "label": "trade_count",
                }
            )

        return {
            "daily_counts": daily_counts,
            "total_trades": int(summary_row.total_trades or 0),
            "total_value": float(summary_row.total_value or 0.0),
            "total_commission": float(summary_row.total_commission or 0.0),
            "buy_trades": int(summary_row.buy_trades or 0),
            "sell_trades": int(summary_row.sell_trades or 0),
        }
