from __future__ import annotations

import asyncio
import logging

from .manual_execution_persistence import manual_execution_persistence
from .manual_execution_service import manual_execution_service

logger = logging.getLogger(__name__)


async def run_manual_execution_worker(poll_interval: float = 1.0) -> None:
    """轮询 trade_manual_execution_tasks，执行 queued 的手动任务。"""
    interval = max(0.2, float(poll_interval or 1.0))
    logger.info("manual execution worker started, poll_interval=%s", interval)
    try:
        while True:
            try:
                task = await manual_execution_persistence.claim_next_queued_task()
                if task is None:
                    await asyncio.sleep(interval)
                    continue
                await manual_execution_service.process_task(task)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("manual execution worker loop failed: %s", exc, exc_info=True)
                await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("manual execution worker cancelled")
        raise

