"""
Daily settlement task for real-account daily ledgers.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

from backend.shared.database_manager_v2 import get_db_manager

from .real_account_ledger_service import finalize_real_account_daily_ledgers

logger = logging.getLogger(__name__)
_SH_TZ = ZoneInfo("Asia/Shanghai")


async def _run_finalize(snapshot_date):
    db_manager = get_db_manager()
    async with db_manager.get_master_session() as db:
        finalized_rows = await finalize_real_account_daily_ledgers(
            db,
            snapshot_date=snapshot_date,
        )
        await db.commit()
        return finalized_rows


async def run_real_account_ledger_settlement_task(
    interval_seconds: int = 600,
    target_time: dt_time = dt_time(15, 5, 0),
):
    logger.info("Starting real-account ledger settlement task...")
    last_finalized_date = None

    now = datetime.now(_SH_TZ)
    if now.time() >= target_time:
        try:
            finalized_rows = await _run_finalize(now.date())
            last_finalized_date = now.date()
            logger.info(
                "Initial catch-up real-account ledger settlement finished date=%s rows=%d",
                now.date().isoformat(),
                finalized_rows,
            )
        except Exception as exc:
            logger.error("Initial real-account ledger settlement failed: %s", exc, exc_info=True)

    while True:
        try:
            now = datetime.now(_SH_TZ)
            today = now.date()
            if now.time() >= target_time and last_finalized_date != today:
                finalized_rows = await _run_finalize(today)
                last_finalized_date = today
                logger.info(
                    "Scheduled real-account ledger settlement finished date=%s rows=%d",
                    today.isoformat(),
                    finalized_rows,
                )
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("Real-account ledger settlement task cancelled")
            break
        except Exception as exc:
            logger.error("Real-account ledger settlement task failed: %s", exc, exc_info=True)
            await asyncio.sleep(60)
