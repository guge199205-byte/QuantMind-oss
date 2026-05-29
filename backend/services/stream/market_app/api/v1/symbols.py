"""Symbol API endpoints"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas import SymbolCreate, SymbolListResponse, SymbolResponse
from ...services import SymbolService

router = APIRouter(prefix="/symbols", tags=["symbols"])


@router.post("/", response_model=SymbolResponse, status_code=201)
async def create_symbol(symbol: SymbolCreate, db: AsyncSession = Depends(get_db)):
    """创建交易标的"""
    service = SymbolService(db)

    # 检查是否已存在
    existing = await service.get_symbol(symbol.symbol)
    if existing:
        raise HTTPException(status_code=400, detail="Symbol already exists")

    return await service.create_symbol(symbol)


@router.get("/{symbol}", response_model=SymbolResponse)
async def get_symbol(symbol: str, db: AsyncSession = Depends(get_db)):
    """获取交易标的"""
    service = SymbolService(db)
    db_symbol = await service.get_symbol(symbol)

    if not db_symbol:
        raise HTTPException(status_code=404, detail="Symbol not found")

    return db_symbol


@router.get("/", response_model=SymbolListResponse)
async def list_symbols(
    exchange: str | None = Query(None, description="交易所"),
    market: str | None = Query(None, description="市场类型"),
    is_active: bool | None = Query(None, description="是否活跃"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """查询交易标的列表"""
    service = SymbolService(db)
    symbols = await service.list_symbols(exchange, market, is_active, limit, offset)

    return SymbolListResponse(total=len(symbols), symbols=symbols)


@router.patch("/{symbol}", response_model=SymbolResponse)
async def update_symbol(symbol: str, update_data: dict, db: AsyncSession = Depends(get_db)):
    """更新交易标的"""
    service = SymbolService(db)
    updated = await service.update_symbol(symbol, update_data)

    if not updated:
        raise HTTPException(status_code=404, detail="Symbol not found")

    return updated


@router.delete("/{symbol}", status_code=204)
async def delete_symbol(symbol: str, db: AsyncSession = Depends(get_db)):
    """删除交易标的（软删除）"""
    service = SymbolService(db)
    success = await service.delete_symbol(symbol)

    if not success:
        raise HTTPException(status_code=404, detail="Symbol not found")
