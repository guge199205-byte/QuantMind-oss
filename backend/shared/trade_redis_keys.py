from __future__ import annotations

from collections.abc import Iterable


def normalize_trade_tenant_id(tenant_id: str | None) -> str:
    return str(tenant_id or "").strip() or "default"


def normalize_trade_user_id(user_id: str | int | None) -> str:
    text = str(user_id or "").strip()
    if not text:
        return ""
    if text.isdigit():
        try:
            return str(int(text)).zfill(8)
        except Exception:
            return text.zfill(8)
    return text


def build_trade_account_key(tenant_id: str | None, user_id: str | int | None) -> str:
    return f"trade:account:{normalize_trade_tenant_id(tenant_id)}:{normalize_trade_user_id(user_id)}"


def build_trade_agent_heartbeat_key(tenant_id: str | None, user_id: str | int | None) -> str:
    return f"trade:agent:heartbeat:{normalize_trade_tenant_id(tenant_id)}:{normalize_trade_user_id(user_id)}"


def trade_account_key_candidates(tenant_id: str | None, user_id: str | int | None) -> tuple[str, ...]:
    normalized_tenant = normalize_trade_tenant_id(tenant_id)
    raw_user = str(user_id or "").strip()
    normalized_user = normalize_trade_user_id(user_id)
    keys = [f"trade:account:{normalized_tenant}:{normalized_user}"]
    if raw_user and raw_user != normalized_user:
        keys.append(f"trade:account:{normalized_tenant}:{raw_user}")
    return tuple(dict.fromkeys(keys))


def trade_agent_heartbeat_key_candidates(tenant_id: str | None, user_id: str | int | None) -> tuple[str, ...]:
    normalized_tenant = normalize_trade_tenant_id(tenant_id)
    raw_user = str(user_id or "").strip()
    normalized_user = normalize_trade_user_id(user_id)
    keys = [f"trade:agent:heartbeat:{normalized_tenant}:{normalized_user}"]
    if raw_user and raw_user != normalized_user:
        keys.append(f"trade:agent:heartbeat:{normalized_tenant}:{raw_user}")
    return tuple(dict.fromkeys(keys))


def pick_first_matching_key(
    getter,
    candidates: Iterable[str],
):
    for key in candidates:
        value = getter(key)
        if value:
            return key, value
    return None, None
