"""
策略-回测闭环 API 路由（Celery + 身份隔离）
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.services.engine.auth_context import get_authenticated_identity
from backend.services.engine.services.strategy_loop_persistence import (
    StrategyLoopPersistence,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/strategy-backtest-loop", tags=["strategy-backtest-loop"])
_persistence = StrategyLoopPersistence()
_tables_ready = False


async def _ensure_tables() -> None:
    global _tables_ready
    if _tables_ready:
        return
    await _persistence.ensure_tables()
    _tables_ready = True


class StrategyBacktestLoopRequest(BaseModel):
    prompt: str = Field(..., description="策略描述")
    strategy_type: str | None = Field(None, description="策略类型")
    complexity_level: str | None = Field("intermediate", description="复杂度级别")
    target_assets: list[str] = Field(default_factory=list, description="目标资产")
    timeframe: str = Field("1d", description="时间周期")
    risk_tolerance: str = Field("medium", description="风险偏好")
    max_iterations: int = Field(10, description="最大迭代次数")
    backtest_period: str = Field("2y", description="回测周期")
    initial_capital: float = Field(100000, description="初始资金")
    custom_requirements: list[str] = Field(default_factory=list, description="自定义要求")


class LoopStatusResponse(BaseModel):
    task_id: str
    status: str
    current_iteration: int
    total_iterations: int
    current_stage: str
    progress_percentage: float
    best_score: float
    estimated_time_remaining: int | None = None
    errors: list[str] = []


class LoopResultResponse(BaseModel):
    task_id: str
    success: bool
    total_iterations: int
    best_strategy: dict[str, Any]
    performance_metrics: dict[str, float]
    learning_insights: dict[str, Any]
    execution_time: float
    all_iterations: list[dict[str, Any]]


def _get_celery_app():
    from qlib_app.celery_config import celery_app

    return celery_app


@router.post("/start", response_model=dict[str, str])
async def start_strategy_backtest_loop(request: StrategyBacktestLoopRequest, req: Request):
    auth_user_id, auth_tenant_id = get_authenticated_identity(req)
    await _ensure_tables()
    try:
        from backend.services.engine.tasks.celery_tasks import run_strategy_backtest_loop

        task_id = str(uuid.uuid4())
        payload = request.model_dump()
        payload["_owner_user_id"] = auth_user_id
        payload["_owner_tenant_id"] = auth_tenant_id
        await _persistence.create_task(
            task_id=task_id,
            user_id=auth_user_id,
            tenant_id=auth_tenant_id,
            status="pending",
            created_at=datetime.now(),
            request_payload=payload,
        )
        run_strategy_backtest_loop.apply_async(args=[task_id, payload], task_id=task_id)
        return {"task_id": task_id, "status": "started"}
    except Exception as e:
        logger.error("Failed to enqueue strategy-backtest loop: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}", response_model=LoopStatusResponse)
async def get_loop_status(task_id: str, req: Request):
    auth_user_id, auth_tenant_id = get_authenticated_identity(req)
    await _ensure_tables()
    task_row = await _persistence.get_task(task_id, user_id=auth_user_id, tenant_id=auth_tenant_id)
    if task_row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    celery_app = _get_celery_app()
    async_result = celery_app.AsyncResult(task_id)
    info = async_result.info if isinstance(async_result.info, dict) else {}

    state_to_status = {
        "PENDING": "pending",
        "RECEIVED": "running",
        "STARTED": "running",
        "RETRY": "running",
        "SUCCESS": "completed",
        "FAILURE": "failed",
        "REVOKED": "cancelled",
    }
    status = task_row.get("status") or state_to_status.get(async_result.state, async_result.state.lower())

    return LoopStatusResponse(
        task_id=task_id,
        status=str(status),
        current_iteration=int(info.get("current_iteration", 0) or 0),
        total_iterations=int(info.get("total_iterations", 0) or 0),
        current_stage=str(info.get("current_stage", "")),
        progress_percentage=float(info.get("progress_percentage", 0.0) or 0.0),
        best_score=float(info.get("best_score", 0.0) or 0.0),
        estimated_time_remaining=info.get("estimated_time_remaining"),
        errors=list(info.get("errors", [])) if isinstance(info.get("errors"), list) else [],
    )


@router.get("/result/{task_id}", response_model=LoopResultResponse)
async def get_loop_result(task_id: str, req: Request):
    auth_user_id, auth_tenant_id = get_authenticated_identity(req)
    await _ensure_tables()
    task_row = await _persistence.get_task(task_id, user_id=auth_user_id, tenant_id=auth_tenant_id)
    if task_row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    payload = task_row.get("result_json") or {}
    if not payload:
        celery_app = _get_celery_app()
        async_result = celery_app.AsyncResult(task_id)
        if not async_result.ready():
            raise HTTPException(status_code=400, detail="Task not completed yet")
        if not async_result.successful():
            detail = str(async_result.info) if async_result.info else "Task failed"
            raise HTTPException(status_code=500, detail=detail)
        payload = async_result.result or {}

    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Invalid task result payload")

    return LoopResultResponse(
        task_id=task_id,
        success=bool(payload.get("success", False)),
        total_iterations=int(payload.get("total_iterations", 0) or 0),
        best_strategy=dict(payload.get("best_strategy") or {}),
        performance_metrics=dict(payload.get("performance_metrics") or {}),
        learning_insights=dict(payload.get("learning_insights") or {}),
        execution_time=float(payload.get("execution_time", 0.0) or 0.0),
        all_iterations=list(payload.get("all_iterations") or []),
    )


@router.delete("/task/{task_id}")
async def cancel_loop_task(task_id: str, req: Request):
    auth_user_id, auth_tenant_id = get_authenticated_identity(req)
    await _ensure_tables()
    task_row = await _persistence.get_task(task_id, user_id=auth_user_id, tenant_id=auth_tenant_id)
    if task_row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        celery_app = _get_celery_app()
        celery_app.control.revoke(task_id, terminate=True)
        await _persistence.update_task(task_id=task_id, status="cancelled", updated_at=datetime.now())
        return {"message": "Task cancelled successfully", "task_id": task_id}
    except Exception as e:
        logger.error("Strategy-backtest loop task cancel failed: %s, error: %s", task_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks")
async def list_running_tasks(req: Request):
    auth_user_id, auth_tenant_id = get_authenticated_identity(req)
    await _ensure_tables()
    rows = await _persistence.list_tasks(user_id=auth_user_id, tenant_id=auth_tenant_id, limit=100)
    return {
        "tasks": [
            {
                "task_id": item.get("task_id"),
                "status": item.get("status"),
                "error": item.get("error_message"),
                "created_at": item.get("created_at").isoformat() if item.get("created_at") else None,
                "updated_at": item.get("updated_at").isoformat() if item.get("updated_at") else None,
            }
            for item in rows
        ]
    }


@router.get("/config/templates")
async def get_loop_templates():
    templates = {
        "conservative": {
            "name": "保守型策略",
            "description": "低风险，稳健收益",
            "config": {
                "max_iterations": 8,
                "risk_tolerance": "low",
                "initial_capital": 100000,
            },
        },
        "balanced": {
            "name": "平衡型策略",
            "description": "风险收益平衡",
            "config": {
                "max_iterations": 10,
                "risk_tolerance": "medium",
                "initial_capital": 100000,
            },
        },
        "aggressive": {
            "name": "激进型策略",
            "description": "高风险，高收益",
            "config": {
                "max_iterations": 15,
                "risk_tolerance": "high",
                "initial_capital": 100000,
            },
        },
    }
    return {"templates": templates}
