"""Qlib 运维与任务路由"""

import logging
import os
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from backend.services.engine.qlib_app import get_qlib_service
from backend.services.engine.qlib_app.api.identity import _identity_from_request
from backend.services.engine.qlib_app.api.task_info import _sanitize_task_info
from backend.services.engine.qlib_app.schemas.backtest import HealthCheckResponse
from backend.services.engine.qlib_app.websocket.connection_manager import ws_manager
from backend.shared.utils import normalize_user_id
from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

router = APIRouter(tags=["qlib"])

logger = logging.getLogger(__name__)
task_logger = StructuredTaskLogger(logger, "OpsAPI")


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    service: Any = Depends(get_qlib_service),
) -> HealthCheckResponse:
    """健康检查"""
    try:
        health = service.check_health()

        db_ok = False
        try:
            from backend.services.engine.qlib_app.services.backtest_persistence import (
                BacktestPersistence,
            )

            db_ok = await BacktestPersistence().check_db()
        except Exception:
            db_ok = False

        redis_ok = False
        try:
            import redis

            r = redis.Redis(
                host=os.getenv("REDIS_HOST", "host.docker.internal"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                password=os.getenv("REDIS_PASSWORD"),
                db=int(os.getenv("REDIS_DB", os.getenv("REDIS_DB_DEFAULT", 0))),
                socket_timeout=1,
            )
            redis_ok = r.ping()
        except Exception:
            redis_ok = False

        return HealthCheckResponse(
            **health,
            db_ok=db_ok,
            redis_ok=redis_ok,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}/status")
async def get_task_status(task_id: str) -> dict[str, Any]:
    """
    通过 Celery 任务 ID 获取任务状态
    """
    from backend.services.engine.qlib_app.tasks import get_backtest_status

    try:
        status = get_backtest_status(task_id)
        raw_info = status.get("info") or {}
        info = _sanitize_task_info(raw_info)
        if not isinstance(info, dict):
            info = {"raw": info}
        info.setdefault("optimization_id", info.get("optimization_id"))
        info.setdefault("total_tasks", info.get("total_tasks", 0))
        info.setdefault("completed_count", info.get("completed_count", 0))
        info.setdefault("failed_count", info.get("failed_count", 0))
        info.setdefault("current_params", info.get("current_params"))
        info.setdefault("best_params", info.get("best_params") or {})
        status["info"] = info
        return status
    except Exception as e:
        task_logger.exception("get_task_status_failed", "获取任务状态失败", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")


@router.post("/task/{task_id}/stop")
async def stop_task(request: Request, task_id: str) -> dict[str, Any]:
    """
    停止异步任务。
    兼容回测与参数优化两类 Celery 任务：先撤销任务，再按任务归属更新持久化状态。
    """
    auth_user_id, auth_tenant_id = _identity_from_request(request)
    cancelled = False

    try:
        from backend.services.engine.qlib_app.tasks import celery_app

        celery_app.control.revoke(task_id, terminate=True)
        cancelled = True
    except Exception as exc:
        task_logger.warning("revoke_celery_task_failed", "Failed to revoke celery task", task_id=task_id, error=str(exc))

    # 优化任务：通过 task_id 反查 optimization_id，再更新状态
    try:
        from backend.services.engine.qlib_app.services.optimization_persistence import OptimizationPersistence

        optimization_persistence = OptimizationPersistence()
        optimization_id = await optimization_persistence.get_optimization_id_by_task_id(task_id)
        if optimization_id:
            detail = await optimization_persistence.get_detail(
                optimization_id,
                user_id=auth_user_id,
                tenant_id=auth_tenant_id,
            )
            if detail is None:
                raise HTTPException(status_code=403, detail="未授权访问该任务")
            await optimization_persistence.update_run(
                optimization_id,
                status="cancelled",
                error_message="Task cancelled by user",
            )
            cancelled = True
    except HTTPException:
        raise
    except Exception as exc:
        task_logger.warning("mark_optimization_cancelled_failed", "Failed to mark optimization task cancelled", task_id=task_id, error=str(exc))

    # 回测任务：直接按 task_id 更新 qlib_backtest_runs
    try:
        from sqlalchemy import text

        from backend.shared.database_manager_v2 import get_session

        async with get_session() as session:
            row = await session.execute(
                text(
                    "SELECT backtest_id, user_id, tenant_id "
                    "FROM qlib_backtest_runs WHERE task_id = :task_id"
                ),
                {"task_id": task_id},
            )
            data = row.mappings().first()
            if data:
                if normalize_user_id(str(data["user_id"])) != normalize_user_id(auth_user_id) or str(
                    data["tenant_id"]
                ) != str(auth_tenant_id):
                    raise HTTPException(status_code=403, detail="未授权访问该任务")
                await session.execute(
                    text(
                        "UPDATE qlib_backtest_runs "
                        "SET status = :status, completed_at = :completed_at "
                        "WHERE task_id = :task_id"
                    ),
                    {
                        "task_id": task_id,
                        "status": "cancelled",
                        "completed_at": datetime.now(),
                    },
                )
                cancelled = True
    except HTTPException:
        raise
    except Exception as exc:
        task_logger.warning("mark_backtest_cancelled_failed", "Failed to mark backtest task cancelled", task_id=task_id, error=str(exc))

    if not cancelled:
        raise HTTPException(status_code=404, detail="Task not found")

    return {"message": "Task cancelled successfully", "task_id": task_id}


@router.get("/logs/{backtest_id}")
async def get_backtest_logs(
    request: Request,
    backtest_id: str,
    start_index: int = Query(0, ge=0, description="日志起始索引"),
    tenant_id: str | None = Query(None, description="租户ID（已废弃，自动使用认证身份）"),
) -> dict[str, Any]:
    """
    获取回测任务日志 (从 Redis 读取)
    """
    try:
        _auth_user_id, auth_tenant_id = _identity_from_request(request, provided_tenant_id=tenant_id)
        import redis

        redis_host = os.getenv("REDIS_HOST", "host.docker.internal")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_password = os.getenv("REDIS_PASSWORD")
        redis_db = int(os.getenv("REDIS_DB", os.getenv("REDIS_DB_DEFAULT", 0)))

        r = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
            decode_responses=True,
        )
        key = f"qlib:logs:{auth_tenant_id}:{backtest_id}"
        length = r.llen(key)
        logs = []
        if start_index < length:
            logs = r.lrange(key, start_index, -1)

        return {
            "backtest_id": backtest_id,
            "logs": logs,
            "next_index": start_index + len(logs),
            "total_length": length,
        }
    except HTTPException:
        raise
    except Exception as e:
        task_logger.exception("fetch_logs_failed", "Fetch logs failed", error=str(e))
        raise HTTPException(status_code=503, detail=f"日志服务不可用: {e}")


@router.post("/progress")
async def receive_progress(data: dict[str, Any] = Body(...)):
    """
    接收内部服务（如 Celery Worker）发送的进度更新，并通过 WebSocket 广播
    """
    backtest_id = data.get("backtest_id")
    if not backtest_id:
        return {"status": "ignored", "reason": "no backtest_id"}

    if data.get("type") == "log":
        message = data.get("message", "")
        if message:
            await ws_manager.broadcast_log(backtest_id, message)
        return {"status": "ok"}

    await ws_manager.broadcast_to_room(data, backtest_id)
    return {"status": "ok"}


@router.post("/log_error")
async def log_frontend_error_endpoint(
    request: Request,
    error_data: dict[str, Any] = Body(...),
):
    """
    接收前端报错并转发给 Worker 日志
    """
    try:
        auth_user_id, auth_tenant_id = _identity_from_request(
            request,
            provided_user_id=error_data.get("user_id"),
            provided_tenant_id=error_data.get("tenant_id"),
        )
        error_data["user_id"] = auth_user_id
        error_data["tenant_id"] = auth_tenant_id

        from backend.services.engine.qlib_app.tasks import log_frontend_error

        log_frontend_error.apply_async(args=[error_data])
        return {"status": "ok"}
    except Exception as e:
        task_logger.exception("forward_frontend_error_failed", "转发前端错误日志失败", error=str(e))
        return {"status": "error", "message": str(e)}
