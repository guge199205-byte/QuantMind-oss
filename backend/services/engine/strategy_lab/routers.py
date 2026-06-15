"""Strategy Lab FastAPI router — sync run + status SSE + result fetch.

Day-2 endpoints (the rest land in Day-5):
- POST   /strategy-lab/run             sync run, returns RunResult
- POST   /strategy-lab/run/async       async submit, returns {run_id}
- GET    /strategy-lab/run/{id}/status SSE progress events
- GET    /strategy-lab/run/{id}/result final RunResult JSON
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .cron.daily_scan import (
    add_watch,
    fetch_latest_signals,
    list_watch,
    remove_watch,
    run_daily_scan,
)
from .overfit import run_overfit_check
from .runner.ast_checker import ASTCheckError
from .runner.progress import ProgressReader, RunStatus
from .runner.result_collector import compute_script_sha, fetch_result
from .runner.subprocess_runner import RunRequest, run_sync, submit_run
from .translator import translate_sdk_to_template

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategy-lab", tags=["strategy-lab"])


class RunBody(BaseModel):
    code: str = Field(..., description="Python script source")
    params: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    qlib_data_path: str | None = None
    drawn_lines: dict[str, float] = Field(
        default_factory=dict,
        description="User-drawn price lines from the K-line UI; readable via ctx.drawn_line(name).",
    )
    timeout_sec: int | None = None


@router.post("/run")
async def post_run(body: RunBody) -> dict[str, Any]:
    req = RunRequest(
        code=body.code,
        params=body.params,
        options=body.options,
        qlib_data_path=body.qlib_data_path,
        drawn_lines=body.drawn_lines or {},
    )
    result = await run_sync(req, timeout_sec=body.timeout_sec)
    return result.to_dict()


@router.post("/run/async")
async def post_run_async(body: RunBody) -> dict[str, Any]:
    req = RunRequest(
        code=body.code,
        params=body.params,
        options=body.options,
        qlib_data_path=body.qlib_data_path,
        drawn_lines=body.drawn_lines or {},
    )
    run_id = await submit_run(req, timeout_sec=body.timeout_sec)
    return {"run_id": run_id, "status": "queued"}


@router.get("/run/{run_id}/status")
async def get_run_status(
    run_id: str,
    last_index: int = Query(0, ge=0),
) -> StreamingResponse:
    """Server-Sent Events stream of ProgressEvent JSON lines."""

    async def gen() -> Any:
        reader = ProgressReader(run_id=run_id)
        idx = last_index
        terminal = {RunStatus.success.value, RunStatus.failed.value, RunStatus.cancelled.value}
        while True:
            events = reader.fetch_events(start=idx, end=-1)
            for evt in events:
                yield f"data: {evt.to_json()}\n\n"
            idx += len(events)
            meta = reader.fetch_meta()
            status = meta.get("status")
            if status in terminal:
                yield f"data: {json.dumps({'final': True, 'status': status})}\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/run/{run_id}/result")
async def get_run_result(run_id: str) -> dict[str, Any]:
    result = fetch_result(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"run_id={run_id} not found or expired")
    return result.to_dict()


# ---------------------------------------------------------------------------
# Day 11-12: 4-gate overfit detection
# ---------------------------------------------------------------------------
class OverfitBody(BaseModel):
    code: str = Field(..., description="Python script source")
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/overfit-check")
async def post_overfit_check(body: OverfitBody) -> dict[str, Any]:
    """Run 4 gates (train/test, walkforward, param sense, monte carlo).

    Returns the OverfitReport dict; the front-end ScoreCard re-uses it.
    """
    try:
        # Run synchronously in a thread so the event loop isn't blocked.
        report = await asyncio.to_thread(run_overfit_check, body.code)
    except ASTCheckError as e:
        raise HTTPException(status_code=400, detail=f"AST 检查未通过：{e}")
    except Exception as e:
        logger.exception("overfit-check failed")
        raise HTTPException(status_code=500, detail=f"4 关卡检测失败：{e}")
    return report.to_dict()


# ---------------------------------------------------------------------------
# Day 15: Translate SDK code → strategy template, save to user library
# ---------------------------------------------------------------------------
class TranslateBody(BaseModel):
    code: str = Field(..., description="Python script source")
    run_id: str | None = None


@router.post("/translate")
async def post_translate(body: TranslateBody, request: Request) -> dict[str, Any]:
    """Translate SDK script → savable strategy template; persist via storage."""
    try:
        template = await asyncio.to_thread(translate_sdk_to_template, body.code, run_id=body.run_id)
    except ASTCheckError as e:
        raise HTTPException(status_code=400, detail=f"AST 检查未通过：{e}")
    except Exception as e:
        logger.exception("translate failed")
        raise HTTPException(status_code=500, detail=f"转模板失败：{e}")

    # Resolve user_id; engine service typically passes JWT through
    user_id = "0"
    try:
        user_id = str(getattr(request.state, "user_id", None) or "0")
    except Exception:
        pass
    if user_id == "0":
        # Fallback: read from header for headless calls
        user_id = request.headers.get("X-User-Id", "0")

    try:
        from backend.shared.strategy_storage import get_strategy_storage_service

        storage = get_strategy_storage_service()
        record = await storage.save(
            user_id=user_id,
            name=template.name,
            code=template.code,
            metadata=template.to_storage_metadata(),
        )
        strategy_id = str(record.get("id"))
    except Exception as e:
        logger.warning("translate save failed (returning ephemeral template): %s", e)
        strategy_id = ""

    return {
        "strategy_id": strategy_id,
        "strategy_name": template.name,
        "needs_review": template.needs_review,
        "notes": template.notes or [],
        "template": {
            "name": template.name,
            "description": template.description,
            "config": template.config,
            "params": template.params,
        },
    }


# ---------------------------------------------------------------------------
# Day 16: Daily-scan watch list + signals
# ---------------------------------------------------------------------------
class WatchBody(BaseModel):
    code: str = Field(..., description="Python script to register for daily scan")
    name: str = Field(..., description="Display name shown in the dashboard signal card")


@router.post("/watch")
async def post_watch(body: WatchBody, request: Request) -> dict[str, Any]:
    """Register a Lab script for the every-evening cron scan."""
    sha = compute_script_sha(body.code, {})
    user_id = "0"
    try:
        user_id = str(getattr(request.state, "user_id", None) or "0")
    except Exception:
        pass
    if user_id == "0":
        user_id = request.headers.get("X-User-Id", "0")
    add_watch(script_sha=sha, user_id=user_id, name=body.name, code=body.code)
    return {"script_sha": sha, "registered": True}


@router.delete("/watch/{script_sha}")
async def delete_watch(script_sha: str) -> dict[str, Any]:
    remove_watch(script_sha)
    return {"script_sha": script_sha, "registered": False}


@router.get("/watch")
async def get_watch_list() -> dict[str, Any]:
    return {"items": list_watch()}


@router.get("/signals")
async def get_signals() -> dict[str, Any]:
    """Latest scan output for the dashboard signal card."""
    return fetch_latest_signals()


@router.post("/scan/run-now")
async def post_scan_now(lookback_days: int = 7) -> dict[str, Any]:
    """Manual trigger — useful for the cron-not-fired-yet case."""
    try:
        return await asyncio.to_thread(run_daily_scan, lookback_days=lookback_days)
    except Exception as e:
        logger.exception("scan/run-now failed")
        raise HTTPException(status_code=500, detail=f"扫描失败：{e}")


__all__ = ["router"]
