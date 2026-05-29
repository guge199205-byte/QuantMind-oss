"""Qlib 参数优化路由"""

from datetime import datetime
from typing import Any, Dict, List, Union
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.services.engine.qlib_app import get_genetic_optimization_service, get_optimization_service
from backend.services.engine.qlib_app.api.identity import _identity_from_request
from backend.services.engine.qlib_app.schemas.backtest import (
    OptimizationTaskResponse,
    OptimizationHistoryDetail,
    OptimizationHistoryItem,
    QlibGeneticOptimizationRequest,
    QlibGeneticOptimizationResult,
    QlibOptimizationRequest,
    QlibOptimizationResult,
)
from backend.services.engine.qlib_app.services.genetic_optimization_service import GeneticOptimizationService
from backend.services.engine.qlib_app.services.optimization_persistence import OptimizationPersistence
from backend.services.engine.qlib_app.services.optimization_service import OptimizationService
from backend.shared.utils import normalize_user_id

router = APIRouter(tags=["qlib"])

optimization_persistence = OptimizationPersistence()


@router.get(
    "/optimization/history",
    response_model=list[OptimizationHistoryItem],
)
async def get_optimization_history(
    request_ctx: Request,
    tenant_id: str | None = None,
    limit: int = Query(20, ge=1, le=100, description="返回条数"),
) -> list[OptimizationHistoryItem]:
    """获取参数优化历史记录"""
    auth_user_id, auth_tenant_id = _identity_from_request(
        request_ctx,
        provided_tenant_id=tenant_id,
    )
    history = await optimization_persistence.list_history(
        auth_user_id,
        tenant_id=auth_tenant_id,
        limit=limit,
    )
    return history


@router.delete("/optimization/history/clear")
async def clear_optimization_history(
    request_ctx: Request,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """一键清除所有参数优化历史记录"""
    auth_user_id, auth_tenant_id = _identity_from_request(
        request_ctx,
        provided_tenant_id=tenant_id,
    )
    success = await optimization_persistence.clear_history(
        auth_user_id,
        tenant_id=auth_tenant_id,
    )
    return {"success": success, "message": "Optimization history cleared successfully"}


@router.get(
    "/optimization/{optimization_id}",
    response_model=OptimizationHistoryDetail,
)
async def get_optimization_detail(
    request_ctx: Request,
    optimization_id: str,
    tenant_id: str | None = None,
) -> OptimizationHistoryDetail:
    """获取参数优化详情"""
    auth_user_id, auth_tenant_id = _identity_from_request(
        request_ctx,
        provided_tenant_id=tenant_id,
    )
    detail = await optimization_persistence.get_detail(
        optimization_id,
        user_id=auth_user_id,
        tenant_id=auth_tenant_id,
    )
    if not detail:
        raise HTTPException(status_code=404, detail="优化记录不存在")
    return detail


@router.post(
    "/optimize",
    response_model=Union[QlibOptimizationResult, OptimizationTaskResponse],
)
async def run_optimization(
    request_ctx: Request,
    request: QlibOptimizationRequest,
    service: OptimizationService = Depends(get_optimization_service),
    async_mode: bool = False,
) -> QlibOptimizationResult | OptimizationTaskResponse:
    """运行参数优化（网格搜索）"""
    try:
        auth_user_id, auth_tenant_id = _identity_from_request(
            request_ctx,
            provided_user_id=request.base_request.user_id,
            provided_tenant_id=request.base_request.tenant_id,
        )
        request.base_request.user_id = normalize_user_id(auth_user_id)
        request.base_request.tenant_id = auth_tenant_id

        if async_mode:
            from backend.services.engine.qlib_app.tasks import run_optimization_async

            optimization_id = uuid4().hex
            request_dict = request.dict()
            request_dict["optimization_id"] = optimization_id
            task = run_optimization_async.apply_async(args=[request_dict])
            await optimization_persistence.create_run(
                optimization_id=optimization_id,
                task_id=task.id,
                mode="grid_search",
                user_id=request.base_request.user_id,
                tenant_id=request.base_request.tenant_id,
                status="pending",
                base_request=request.base_request.model_dump(mode="json"),
                config_snapshot={
                    "base_request": request.base_request.model_dump(mode="json"),
                    "param_ranges": [item.model_dump(mode="json") for item in request.param_ranges],
                    "optimization_target": request.optimization_target,
                    "max_parallel": request.max_parallel,
                },
                optimization_target=request.optimization_target,
                param_ranges=[item.model_dump(mode="json") for item in request.param_ranges],
                total_tasks=request.total_combinations(),
            )

            return OptimizationTaskResponse(
                optimization_id=optimization_id,
                task_id=task.id,
                status="pending",
                created_at=datetime.now(),
            )

        return await service.run_optimization(request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"优化执行失败: {str(e)}")


@router.post(
    "/optimize/genetic",
    response_model=Union[QlibGeneticOptimizationResult, OptimizationTaskResponse],
)
async def run_genetic_optimization(
    request_ctx: Request,
    request: QlibGeneticOptimizationRequest,
    service: GeneticOptimizationService = Depends(get_genetic_optimization_service),
    async_mode: bool = False,
) -> QlibGeneticOptimizationResult | OptimizationTaskResponse:
    """运行遗传算法参数优化"""
    try:
        auth_user_id, auth_tenant_id = _identity_from_request(
            request_ctx,
            provided_user_id=request.base_request.user_id,
            provided_tenant_id=request.base_request.tenant_id,
        )
        request.base_request.user_id = normalize_user_id(auth_user_id)
        request.base_request.tenant_id = auth_tenant_id

        if async_mode:
            from backend.services.engine.qlib_app.tasks import run_genetic_optimization_async

            optimization_id = request.optimization_id
            request_dict = request.dict()
            task = run_genetic_optimization_async.apply_async(args=[request_dict])

            return OptimizationTaskResponse(
                optimization_id=optimization_id,
                task_id=task.id,
                status="pending",
                created_at=datetime.now(),
            )

        return await service.run_optimization(request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"遗传算法优化失败: {str(e)}")
