from __future__ import annotations

import json
import logging
from typing import Any

from backend.shared.trade_redis_keys import (
    build_trade_account_key,
    build_trade_agent_heartbeat_key,
)

logger = logging.getLogger(__name__)


def _resolve_redis_client(redis_like: Any):
    if redis_like is None:
        return None
    client = getattr(redis_like, "client", None)
    return client or redis_like


def write_json_cache(redis_like: Any, key: str, payload: dict[str, Any]) -> str:
    client = _resolve_redis_client(redis_like)
    if client is None:
        return key
    try:
        client.set(key, json.dumps(payload or {}, ensure_ascii=False))
    except Exception as exc:
        logger.warning("Failed to write json cache: key=%s err=%s", key, exc)
    return key


def read_json_cache(redis_like: Any, key: str) -> dict[str, Any] | None:
    client = _resolve_redis_client(redis_like)
    if client is None:
        return None
    try:
        raw = client.get(key)
        if not raw:
            return None
        if isinstance(raw, dict):
            return raw
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except Exception as exc:
        logger.warning("Failed to read json cache: key=%s err=%s", key, exc)
        return None


def write_trade_account_cache(redis_like: Any, tenant_id: str, user_id: str | int, payload: dict[str, Any]) -> str:
    key = build_trade_account_key(tenant_id, user_id)
    return write_json_cache(redis_like, key, payload)


def write_trade_agent_heartbeat_cache(
    redis_like: Any,
    tenant_id: str,
    user_id: str | int,
    payload: dict[str, Any],
) -> str:
    key = build_trade_agent_heartbeat_key(tenant_id, user_id)
    return write_json_cache(redis_like, key, payload)
