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

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .runner.progress import ProgressReader, RunStatus
from .runner.result_collector import fetch_result
from .runner.subprocess_runner import RunRequest, run_sync, submit_run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategy-lab", tags=["strategy-lab"])


class RunBody(BaseModel):
    code: str = Field(..., description="Python script source")
    params: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    qlib_data_path: str | None = None
    timeout_sec: int | None = None


@router.post("/run")
async def post_run(body: RunBody) -> dict[str, Any]:
    req = RunRequest(
        code=body.code,
        params=body.params,
        options=body.options,
        qlib_data_path=body.qlib_data_path,
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


__all__ = ["router"]
