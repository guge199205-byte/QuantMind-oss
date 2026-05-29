"""Symbol service"""

import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Symbol
from ..schemas import SymbolCreate, SymbolResponse

logger = logging.getLogger(__name__)


class SymbolService:
    """交易标的服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_symbol(self, symbol: SymbolCreate) -> SymbolResponse:
        """创建交易标的"""
        db_symbol = Symbol(**symbol.model_dump())
        self.db.add(db_symbol)
        await self.db.commit()
        await self.db.refresh(db_symbol)
        return SymbolResponse.model_validate(db_symbol)

    async def get_symbol(self, symbol: str) -> SymbolResponse | None:
        """获取交易标的"""
        query = select(Symbol).filter(Symbol.symbol == symbol)
        result = await self.db.execute(query)
        db_symbol = result.scalar_one_or_none()

        return SymbolResponse.model_validate(db_symbol) if db_symbol else None

    async def list_symbols(
        self,
        exchange: str | None = None,
        market: str | None = None,
        is_active: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SymbolResponse]:
        """查询交易标的列表"""
        query = select(Symbol)

        if exchange:
            query = query.filter(Symbol.exchange == exchange)
        if market:
            query = query.filter(Symbol.market == market)
        if is_active is not None:
            query = query.filter(Symbol.is_active == is_active)

        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        symbols = result.scalars().all()

        return [SymbolResponse.model_validate(s) for s in symbols]

    async def update_symbol(self, symbol: str, update_data: dict) -> SymbolResponse | None:
        """更新交易标的"""
        query = select(Symbol).filter(Symbol.symbol == symbol)
        result = await self.db.execute(query)
        db_symbol = result.scalar_one_or_none()

        if not db_symbol:
            return None

        for key, value in update_data.items():
            if hasattr(db_symbol, key):
                setattr(db_symbol, key, value)

        await self.db.commit()
        await self.db.refresh(db_symbol)

        return SymbolResponse.model_validate(db_symbol)

    async def delete_symbol(self, symbol: str) -> bool:
        """删除交易标的（软删除）"""
        return await self.update_symbol(symbol, {"is_active": False}) is not None
