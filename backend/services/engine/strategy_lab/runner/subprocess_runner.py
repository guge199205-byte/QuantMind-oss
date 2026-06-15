"""Subprocess orchestrator — spawns worker.py per run.

API process calls ``submit_run(request)``; the worker runs in a separate
Python process so user code is sandboxed (Layer 2). All state flows through
Redis (qm:lab:run:{id} / qm:lab:progress:{id} / qm:lab:result:{id}).

Day-2 scope: blocking ``run_sync`` for the validation gate and the
non-blocking ``submit_run`` used by the SSE endpoint. Cancellation,
cgroup limits and Docker-layer 3 are Day-7+ work.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .progress import (
    Phase,
    ProgressPublisher,
    ProgressReader,
    RunStatus,
    meta_key,
    script_key,
    _TTL_SECONDS,
)
from .result_collector import RunResult, fetch_result

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 60
WORKER_MODULE = "backend.services.engine.strategy_lab.runner.worker"


@dataclass
class RunRequest:
    code: str
    params: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)
    user_id: str | None = None
    qlib_data_path: str | None = None
    drawn_lines: dict[str, float] = field(default_factory=dict)
    run_id: str = ""

    def __post_init__(self) -> None:
        if not self.run_id:
            self.run_id = uuid.uuid4().hex


def _safe_env() -> dict[str, str]:
    """Strip secrets — only pass through Redis + Python paths."""
    keep = {
        "PATH",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "LANG",
        "LC_ALL",
        "HOME",
        "TZ",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_PASSWORD",
        "REDIS_DB",
        "REDIS_SENTINEL_HOSTS",
        "REDIS_SENTINEL_SERVICE_NAME",
        "QLIB_DATA_PATH",
    }
    env = {k: v for k, v in os.environ.items() if k in keep}
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


async def submit_run(req: RunRequest, *, timeout_sec: int | None = None) -> str:
    """Spawn worker process and return the run_id immediately.

    Caller is expected to consume progress + result via the Redis keys.
    The subprocess itself runs in the background; this coroutine returns
    once the worker has been launched (it does not await completion).
    """
    publisher = ProgressPublisher(run_id=req.run_id)
    publisher.set_status(RunStatus.queued, queued_at=time.time())
    publisher.publish(Phase.queued, 0.0, "queued")
    _persist_script(req)

    payload = {
        "run_id": req.run_id,
        "code": req.code,
        "params": req.params,
        "qlib_data_path": req.qlib_data_path,
        "drawn_lines": req.drawn_lines or {},
    }
    timeout = timeout_sec or req.options.get("timeout_sec") or DEFAULT_TIMEOUT_SEC

    asyncio.create_task(_run_worker(payload, timeout))
    return req.run_id


async def run_sync(req: RunRequest, *, timeout_sec: int | None = None) -> RunResult:
    """Spawn worker and block until it returns. Day-2 validation entrypoint."""
    publisher = ProgressPublisher(run_id=req.run_id)
    publisher.set_status(RunStatus.queued, queued_at=time.time())
    publisher.publish(Phase.queued, 0.0, "queued")
    _persist_script(req)

    payload = {
        "run_id": req.run_id,
        "code": req.code,
        "params": req.params,
        "qlib_data_path": req.qlib_data_path,
        "drawn_lines": req.drawn_lines or {},
    }
    timeout = timeout_sec or req.options.get("timeout_sec") or DEFAULT_TIMEOUT_SEC

    rc, stdout, stderr = await _run_worker(payload, timeout)
    result = fetch_result(req.run_id)
    if result is None:
        result = RunResult(
            run_id=req.run_id,
            status="failed",
            error=f"worker exited rc={rc} without writing result; stderr={stderr[-512:]}",
        )
    return result


async def _run_worker(
    payload: dict[str, Any],
    timeout_sec: int,
) -> tuple[int, str, str]:
    """Launch ``python -m strategy_lab.runner.worker`` and feed JSON via stdin."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        WORKER_MODULE,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_safe_env(),
        cwd="/tmp",
    )
    raw = json.dumps(payload).encode("utf-8")
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(input=raw), timeout=timeout_sec
        )
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass
        publisher = ProgressPublisher(run_id=payload["run_id"])
        publisher.publish(
            Phase.done, 100.0,
            f"timed out after {timeout_sec}s",
        )
        publisher.set_status(RunStatus.failed, error="timeout")
        return -9, "", "timeout"
    return (
        proc.returncode or 0,
        stdout_b.decode("utf-8", errors="replace") if stdout_b else "",
        stderr_b.decode("utf-8", errors="replace") if stderr_b else "",
    )


def _persist_script(req: RunRequest) -> None:
    """Stash the script body under qm:lab:script:{run_id} for repro."""
    try:
        from backend.shared.redis_sentinel_client import get_redis_sentinel_client
        r = get_redis_sentinel_client()
        r.set(
            script_key(req.run_id),
            req.code.encode("utf-8"),
            ex=_TTL_SECONDS,
        )
    except Exception as e:
        logger.warning("persist_script run_id=%s: %s", req.run_id, e)


__all__ = ["RunRequest", "submit_run", "run_sync", "DEFAULT_TIMEOUT_SEC"]
