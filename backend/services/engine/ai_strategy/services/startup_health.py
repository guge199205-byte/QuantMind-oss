"""AI Strategy 启动健康检查与预热状态管理。"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StartupHealthReport:
    """启动阶段健康检查结果。"""

    ready: bool = False
    qwen_provider_ready: bool = False
    vector_parser_ready: bool = False
    schema_retriever_ready: bool = False
    elapsed_seconds: float = 0.0
    error: str | None = None


_STARTUP_HEALTH_REPORT = StartupHealthReport()


def get_startup_health_report() -> dict[str, Any]:
    """返回最近一次启动健康检查快照。"""

    return asdict(_STARTUP_HEALTH_REPORT)


def _store_startup_health_report(report: StartupHealthReport) -> None:
    global _STARTUP_HEALTH_REPORT
    _STARTUP_HEALTH_REPORT = report


async def _warmup_strategy_dependencies() -> None:
    from ..provider_registry import get_provider
    from .selection.schema_retriever import get_schema_retriever
    from .selection.vector_parser import get_strategy_vector_parser

    get_provider()
    await get_strategy_vector_parser()
    await get_schema_retriever()


def _warmup_strategy_dependencies_sync() -> None:
    asyncio.run(_warmup_strategy_dependencies())


async def run_startup_health_checks(timeout_seconds: float | None = None) -> StartupHealthReport:
    """强制预热 AI Strategy 依赖，失败则阻断启动。"""

    report = StartupHealthReport()
    started_at = time.monotonic()

    if timeout_seconds is None:
        timeout_raw = os.getenv("AI_STRATEGY_WARMUP_TIMEOUT_SECONDS", "60").strip()
        try:
            timeout_seconds = max(1.0, float(timeout_raw))
        except ValueError:
            timeout_seconds = 60.0

    try:
        await asyncio.wait_for(asyncio.to_thread(_warmup_strategy_dependencies_sync), timeout=timeout_seconds)
        report.ready = True
        report.qwen_provider_ready = True
        report.vector_parser_ready = True
        report.schema_retriever_ready = True
        logger.info("AI Strategy startup health check completed in %.2fs", time.monotonic() - started_at)
        return report
    except Exception as exc:
        report.error = str(exc)
        logger.error("AI Strategy startup health check failed: %s", exc)
        raise RuntimeError(f"AI Strategy startup health check failed: {exc}") from exc
    finally:
        report.elapsed_seconds = round(time.monotonic() - started_at, 2)
        _store_startup_health_report(report)
