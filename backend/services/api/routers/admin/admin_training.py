import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from docker import DockerClient
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text

from backend.services.api.routers.admin.db import TrainingJobRecord
from backend.services.api.user_app.middleware.auth import require_admin
from backend.services.engine.training.local_docker_orchestrator import LocalDockerOrchestrator
from backend.services.engine.training.training_log_stream import TrainingRunLogStream
from backend.shared.database_manager_v2 import get_session
from backend.shared.model_registry import model_registry_service
from .admin_training_utils import *
from .admin_training_utils import _resolve_admin_scope, _SetDefaultModelRequest, _SetStrategyBindingRequest

router = APIRouter()
logger = logging.getLogger(__name__)
@router.get("/user-models", summary="管理员查看用户模型列表（兼容别名）")
async def admin_list_user_models(
    tenant_id: str | None = None,
    user_id: str | None = None,
    include_archived: bool = False,
    current_user: dict[str, Any] = Depends(require_admin),
):
    scope_tenant, scope_user = _resolve_admin_scope(
        current_user=current_user,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    items = await model_registry_service.list_models(
        tenant_id=scope_tenant,
        user_id=scope_user,
        include_archived=include_archived,
    )
    return {"tenant_id": scope_tenant, "user_id": scope_user, "items": items, "total": len(items)}


@router.get("/user-models/default", summary="管理员查看用户默认模型（兼容别名）")
async def admin_get_default_model(
    tenant_id: str | None = None,
    user_id: str | None = None,
    current_user: dict[str, Any] = Depends(require_admin),
):
    scope_tenant, scope_user = _resolve_admin_scope(
        current_user=current_user,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    model = await model_registry_service.get_default_model(tenant_id=scope_tenant, user_id=scope_user)
    if not model:
        raise HTTPException(status_code=404, detail="Default model not found")
    return model


@router.patch("/user-models/default", summary="管理员设置用户默认模型（兼容别名）")
async def admin_set_default_model(
    payload: _SetDefaultModelRequest,
    tenant_id: str | None = None,
    user_id: str | None = None,
    current_user: dict[str, Any] = Depends(require_admin),
):
    scope_tenant, scope_user = _resolve_admin_scope(
        current_user=current_user,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    try:
        return await model_registry_service.set_default_model(
            tenant_id=scope_tenant,
            user_id=scope_user,
            model_id=payload.model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/user-models/{model_id}", summary="管理员查看用户单模型（兼容别名）")
async def admin_get_user_model(
    model_id: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
    current_user: dict[str, Any] = Depends(require_admin),
):
    scope_tenant, scope_user = _resolve_admin_scope(
        current_user=current_user,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    model = await model_registry_service.get_model(tenant_id=scope_tenant, user_id=scope_user, model_id=model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.post("/user-models/{model_id}/archive", summary="管理员归档用户模型（兼容别名）")
async def admin_archive_user_model(
    model_id: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
    current_user: dict[str, Any] = Depends(require_admin),
):
    scope_tenant, scope_user = _resolve_admin_scope(
        current_user=current_user,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    try:
        return await model_registry_service.archive_model(
            tenant_id=scope_tenant,
            user_id=scope_user,
            model_id=model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/user-models/strategy-bindings/{strategy_id}",
    summary="管理员查看用户策略模型绑定（兼容别名）",
)
async def admin_get_strategy_binding(
    strategy_id: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
    current_user: dict[str, Any] = Depends(require_admin),
):
    scope_tenant, scope_user = _resolve_admin_scope(
        current_user=current_user,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    binding = await model_registry_service.get_strategy_binding(
        tenant_id=scope_tenant,
        user_id=scope_user,
        strategy_id=strategy_id,
    )
    if not binding:
        raise HTTPException(status_code=404, detail="Strategy binding not found")
    return binding


@router.put(
    "/user-models/strategy-bindings/{strategy_id}",
    summary="管理员设置用户策略模型绑定（兼容别名）",
)
async def admin_set_strategy_binding(
    strategy_id: str,
    payload: _SetStrategyBindingRequest,
    tenant_id: str | None = None,
    user_id: str | None = None,
    current_user: dict[str, Any] = Depends(require_admin),
):
    scope_tenant, scope_user = _resolve_admin_scope(
        current_user=current_user,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    try:
        return await model_registry_service.set_strategy_binding(
            tenant_id=scope_tenant,
            user_id=scope_user,
            strategy_id=strategy_id,
            model_id=payload.model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete(
    "/user-models/strategy-bindings/{strategy_id}",
    summary="管理员解除用户策略模型绑定（兼容别名）",
)
async def admin_delete_strategy_binding(
    strategy_id: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
    current_user: dict[str, Any] = Depends(require_admin),
):
    scope_tenant, scope_user = _resolve_admin_scope(
        current_user=current_user,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    deleted = await model_registry_service.delete_strategy_binding(
        tenant_id=scope_tenant,
        user_id=scope_user,
        strategy_id=strategy_id,
    )
    return {"deleted": bool(deleted), "strategy_id": strategy_id}


@router.post("/run-training", summary="启动云端模型训练任务")
async def run_training(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: dict[str, Any] = Depends(require_admin),
):
    return await submit_training_job(payload, background_tasks, current_user)


@router.get("/training-runs/{run_id}", summary="获取训练任务状态")
async def get_training_run(
    run_id: str,
    current_user: dict[str, Any] = Depends(require_admin),
):
    return await get_training_run_for_owner(run_id, current_user)


@router.post("/training-runs/{run_id}/complete", summary="训练完成回调（内部接口）")
async def training_complete_callback(
    run_id: str,
    result: dict[str, Any],
    x_internal_call_secret: str = Header(default="", alias="X-Internal-Call-Secret"),
):
    return await complete_training_run(run_id, result, x_internal_call_secret)


@router.get("/training-jobs", summary="管理员查看训练任务列表")
async def list_training_jobs(
    status: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size

    filters: list[str] = []
    params: dict[str, Any] = {}

    if status:
        filters.append("status = :status")
        params["status"] = status
    if tenant_id:
        filters.append("tenant_id = :tenant_id")
        params["tenant_id"] = tenant_id
    if user_id:
        filters.append("user_id = :user_id")
        params["user_id"] = user_id

    where_clause = ("WHERE " + " AND ".join(filters)) if filters else ""

    async with get_session(read_only=True) as session:
        total_row = (
            await session.execute(
                text(f"SELECT COUNT(*) FROM admin_training_jobs {where_clause}"),
                params,
            )
        ).scalar_one()

        rows = (
            await session.execute(
                text(
                    f"""
                    SELECT id, tenant_id, user_id, status, progress, instance_id,
                           logs, result, request_payload, created_at, updated_at
                    FROM admin_training_jobs
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {**params, "limit": page_size, "offset": offset},
            )
        ).mappings().all()

    items = []
    for row in rows:
        result_json = row["result"] if isinstance(row["result"], dict) else {}
        req_payload = row["request_payload"] if isinstance(row["request_payload"], dict) else {}
        model_reg = result_json.get("model_registration") or {}
        items.append(
            {
                "run_id": row["id"],
                "tenant_id": row["tenant_id"],
                "user_id": row["user_id"],
                "status": row["status"],
                "progress": int(row["progress"] or 0),
                "instance_id": row["instance_id"],
                "model_type": req_payload.get("model_type", ""),
                "job_name": req_payload.get("job_name", ""),
                "features_count": len(req_payload.get("features") or []),
                "train_start": req_payload.get("train_start", ""),
                "train_end": req_payload.get("train_end", ""),
                "registered_model_id": model_reg.get("model_id") or "",
                "has_logs": bool(str(row["logs"] or "").strip()),
                "created_at": str(row["created_at"] or ""),
                "updated_at": str(row["updated_at"] or ""),
            }
        )

    return {
        "total": int(total_row or 0),
        "page": page,
        "page_size": page_size,
        "items": items,
    }
