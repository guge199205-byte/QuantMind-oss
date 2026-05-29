from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.api.user_app.middleware.auth import get_current_user
from backend.shared.trading_calendar import calendar_service

router = APIRouter(prefix="/api/v1/market-calendar", tags=["Market-Calendar"])


class BatchCheckRequest(BaseModel):
    market: str = Field(..., description="市场代码，如 SSE/SZSE/CFFEX")
    dates: list[date] = Field(..., description="待批量判断日期列表")


def _owner(current_user: dict) -> tuple[str, str]:
    tenant_id = str(current_user.get("tenant_id") or "default")
    user_id = str(current_user.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="无效用户上下文")
    return tenant_id, user_id


@router.get("/is-trading-day")
async def is_trading_day(
    market: str = Query(..., description="市场代码"),
    date_value: date = Query(..., alias="date", description="交易日日期，格式 YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
):
    tenant_id, user_id = _owner(current_user)
    result = await calendar_service.is_trading_day(
        market=market,
        trade_date=date_value,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    return {
        "market": market.upper(),
        "date": date_value.isoformat(),
        "is_trading_day": result,
        "tenant_id": tenant_id,
        "user_id": user_id,
    }


@router.get("/next-trading-day")
async def next_trading_day(
    market: str = Query(..., description="市场代码"),
    date_value: date = Query(..., alias="date", description="基准日期，格式 YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
):
    tenant_id, user_id = _owner(current_user)
    next_day = await calendar_service.next_trading_day(
        market=market,
        trade_date=date_value,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    return {
        "market": market.upper(),
        "base_date": date_value.isoformat(),
        "next_trading_day": next_day.isoformat(),
        "tenant_id": tenant_id,
        "user_id": user_id,
    }


@router.get("/prev-trading-day")
async def prev_trading_day(
    market: str = Query(..., description="市场代码"),
    date_value: date = Query(..., alias="date", description="基准日期，格式 YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
):
    tenant_id, user_id = _owner(current_user)
    prev_day = await calendar_service.prev_trading_day(
        market=market,
        trade_date=date_value,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    return {
        "market": market.upper(),
        "base_date": date_value.isoformat(),
        "prev_trading_day": prev_day.isoformat(),
        "tenant_id": tenant_id,
        "user_id": user_id,
    }


@router.get("/sessions")
async def get_sessions(
    market: str = Query(..., description="市场代码"),
    date_value: date = Query(..., alias="date", description="交易日日期，格式 YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user),
):
    tenant_id, user_id = _owner(current_user)
    sessions = await calendar_service.get_sessions(
        market=market,
        trade_date=date_value,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    return {
        "market": market.upper(),
        "date": date_value.isoformat(),
        "sessions": [x.to_dict() for x in sessions],
        "tenant_id": tenant_id,
        "user_id": user_id,
    }


@router.get("/is-trading-time")
async def is_trading_time(
    market: str = Query(..., description="市场代码"),
    dt: str | None = Query(
        None,
        description="待判断时间，ISO8601；不传则使用当前市场时区时间",
    ),
    current_user: dict = Depends(get_current_user),
):
    tenant_id, user_id = _owner(current_user)
    parsed_dt: datetime | None = None
    if dt:
        try:
            parsed_dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"无效 dt 格式: {dt}") from exc
        if parsed_dt.tzinfo is None:
            parsed_dt = parsed_dt.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    payload = await calendar_service.is_trading_time(
        market=market,
        dt=parsed_dt,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    return {
        "market": market.upper(),
        "datetime": (parsed_dt.isoformat() if parsed_dt else None),
        **payload,
        "tenant_id": tenant_id,
        "user_id": user_id,
    }


@router.post("/batch-check")
async def batch_check(
    request: BatchCheckRequest,
    current_user: dict = Depends(get_current_user),
):
    tenant_id, user_id = _owner(current_user)
    if not request.dates:
        raise HTTPException(status_code=400, detail="dates 不能为空")
    results = await calendar_service.batch_is_trading_day(
        market=request.market,
        dates=request.dates,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    return {
        "market": request.market.upper(),
        "results": results,
        "total": len(results),
        "tenant_id": tenant_id,
        "user_id": user_id,
    }
