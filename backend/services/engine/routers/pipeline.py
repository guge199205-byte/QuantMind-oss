from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from backend.services.engine.auth_context import (
    assert_identity_not_spoofed,
    get_authenticated_identity,
)
from backend.services.engine.services.pipeline_service import (
    PipelineRunRequest,
    PipelineRunResult,
    PipelineRunStatus,
    PipelineService,
)

router = APIRouter()
pipeline_service = PipelineService()


def _enqueue_pipeline_run(run_id: str) -> None:
    from backend.services.engine.tasks.celery_tasks import run_pipeline_run

    run_pipeline_run.apply_async(args=[run_id])


@router.post("/runs", response_model=PipelineRunStatus)
async def create_pipeline_run(payload: PipelineRunRequest, request: Request) -> PipelineRunStatus:
    auth_user_id, auth_tenant_id = get_authenticated_identity(request)
    assert_identity_not_spoofed(
        auth_user_id=auth_user_id,
        auth_tenant_id=auth_tenant_id,
        provided_user_id=payload.user_id,
        provided_tenant_id=payload.tenant_id,
    )
    normalized_payload = payload.model_copy(update={"user_id": auth_user_id, "tenant_id": auth_tenant_id})

    run_id = await pipeline_service.create_run(normalized_payload)
    try:
        _enqueue_pipeline_run(run_id)
    except Exception as exc:
        await pipeline_service._update_run(
            run_id=run_id,
            status="failed",
            stage="failed",
            error=f"failed to enqueue pipeline task: {exc}",
        )
        raise HTTPException(status_code=500, detail="failed to enqueue pipeline task")
    status = await pipeline_service.get_status(run_id, user_id=auth_user_id, tenant_id=auth_tenant_id)
    if status is None:
        raise HTTPException(status_code=500, detail="failed to initialize pipeline run")
    return status


@router.get("/runs/{run_id}", response_model=PipelineRunStatus)
async def get_pipeline_run_status(
    run_id: str,
    request: Request,
    user_id: str | None = Query(None, description="用户ID（已废弃，自动使用认证身份）"),
    tenant_id: str | None = Query(None, description="租户ID（已废弃，自动使用认证身份）"),
) -> PipelineRunStatus:
    auth_user_id, auth_tenant_id = get_authenticated_identity(request)
    assert_identity_not_spoofed(
        auth_user_id=auth_user_id,
        auth_tenant_id=auth_tenant_id,
        provided_user_id=user_id,
        provided_tenant_id=tenant_id,
    )
    status = await pipeline_service.get_status(run_id, user_id=auth_user_id, tenant_id=auth_tenant_id)
    if status is None:
        raise HTTPException(status_code=404, detail="pipeline run not found")
    return status


@router.get("/runs/{run_id}/result", response_model=PipelineRunResult)
async def get_pipeline_run_result(
    run_id: str,
    request: Request,
    user_id: str | None = Query(None, description="用户ID（已废弃，自动使用认证身份）"),
    tenant_id: str | None = Query(None, description="租户ID（已废弃，自动使用认证身份）"),
) -> PipelineRunResult:
    auth_user_id, auth_tenant_id = get_authenticated_identity(request)
    assert_identity_not_spoofed(
        auth_user_id=auth_user_id,
        auth_tenant_id=auth_tenant_id,
        provided_user_id=user_id,
        provided_tenant_id=tenant_id,
    )
    result = await pipeline_service.get_result(run_id, user_id=auth_user_id, tenant_id=auth_tenant_id)
    if result is None:
        status = await pipeline_service.get_status(run_id, user_id=auth_user_id, tenant_id=auth_tenant_id)
        if status is None:
            raise HTTPException(status_code=404, detail="pipeline run not found")
        raise HTTPException(status_code=409, detail="pipeline run still running")
    return result


@router.delete("/runs")
async def cleanup_pipeline_runs(
    request: Request,
    user_id: str | None = Query(None, description="用户ID（已废弃，自动使用认证身份）"),
    tenant_id: str | None = Query(None, description="租户ID（已废弃，自动使用认证身份）"),
    keep_days: int = Query(30, ge=1, le=3650, description="保留天数"),
):
    auth_user_id, auth_tenant_id = get_authenticated_identity(request)
    assert_identity_not_spoofed(
        auth_user_id=auth_user_id,
        auth_tenant_id=auth_tenant_id,
        provided_user_id=user_id,
        provided_tenant_id=tenant_id,
    )
    deleted = await pipeline_service.cleanup_old_runs(
        user_id=auth_user_id, tenant_id=auth_tenant_id, keep_days=keep_days
    )
    return {
        "status": "success",
        "deleted": deleted,
        "keep_days": keep_days,
        "user_id": auth_user_id,
        "tenant_id": auth_tenant_id,
    }
