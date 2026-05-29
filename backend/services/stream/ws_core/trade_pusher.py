#!/usr/bin/env python3
"""
Trading event pusher.
Consumes Redis Stream 'trading_events' and pushes events to
WebSocket clients subscribed to 'trade.updates.{user_id}'.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

import redis.asyncio as aioredis

from ..market_app.market_config import settings
from .manager import manager

logger = logging.getLogger(__name__)

TRADE_EVENTS_STREAM = "trading_events"


import os


def _build_redis_client() -> aioredis.Redis:
    # OSS Edition: 使用统一 Redis 实例
    host = os.getenv("TRADE_EVENTS_REDIS_HOST", settings.REDIS_HOST)
    port = int(os.getenv("TRADE_EVENTS_REDIS_PORT", settings.REDIS_PORT))
    password = os.getenv("TRADE_EVENTS_REDIS_PASSWORD", settings.REDIS_PASSWORD)
    db = int(os.getenv("TRADE_EVENTS_REDIS_DB", "0"))

    if settings.REDIS_USE_SENTINEL:
        from redis.asyncio.sentinel import Sentinel

        sentinel = Sentinel(
            settings.REDIS_SENTINELS,
            socket_timeout=0.5,
            password=password or None,
        )
        return sentinel.master_for(
            settings.REDIS_MASTER_NAME,
            socket_timeout=1.0,
            password=password or None,
            db=db,
        )
    return aioredis.Redis(
        host=host,
        port=port,
        password=password or None,
        db=db,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=5,
    )


class TradePusher:
    """Real-time trade event pusher via Redis Stream -> WebSocket."""

    def __init__(self):
        self.running = False
        self._task: asyncio.Task | None = None
        self._redis: aioredis.Redis | None = None

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._redis = _build_redis_client()
        self._task = asyncio.create_task(self._consume_loop(), name="trade_pusher")
        logger.info("TradePusher started, listening: %s", TRADE_EVENTS_STREAM)

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._redis:
            await self._redis.aclose()
        logger.info("TradePusher stopped")

    async def _consume_loop(self) -> None:
        last_id = "$"
        retry_delay = 1.0

        while self.running:
            try:
                results = await self._redis.xread(
                    {TRADE_EVENTS_STREAM: last_id},
                    block=2000,
                    count=50,
                )
                if results:
                    for _stream, messages in results:
                        for msg_id, data in messages:
                            last_id = msg_id
                            await self._broadcast(data)
                retry_delay = 1.0
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("TradePusher error, retry in %ss: %s", retry_delay, exc)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)
                try:
                    if self._redis:
                        await self._redis.aclose()
                    self._redis = _build_redis_client()
                except Exception:
                    pass

    async def _broadcast(self, raw: dict[str, Any]) -> None:
        user_id = str(raw.get("user_id", "")).strip()
        if not user_id or user_id == "None":
            return

        topic = f"trade.updates.{user_id}"
        message = {
            "type": "trade_update",
            "timestamp": time.time(),
            "data": dict(raw),
        }
        sent = await manager.publish(topic, message)
        if sent:
            logger.info(
                "TradePusher -> topic=%s event=%s sent=%d",
                topic,
                raw.get("event_type"),
                sent,
            )


trade_pusher = TradePusher()
