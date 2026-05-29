"""Qlib 策略名称解析工具"""

from typing import Any, Optional


def _normalize_strategy_key(raw: Any) -> str:
    text = str(raw or "").strip().strip("'").strip('"')
    if not text:
        return ""
    if text.endswith(".py") or text.endswith(".json"):
        text = text.rsplit(".", 1)[0]
    return text


def _resolve_strategy_display_name(payload: dict[str, Any]) -> str | None:
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    candidates = [
        payload.get("strategy_display_name"),
        payload.get("strategy_name"),
        config.get("strategy_display_name"),
        config.get("strategy_name"),
        config.get("qlib_strategy_type"),
        payload.get("qlib_strategy_type"),
        config.get("strategy_type"),
        payload.get("strategy_type"),
    ]
    namespaced_fallback_map = {
        "topkdropout": "默认 Top-K 选股策略",
        "weightstrategy": "截面 Alpha 预测策略",
    }

    try:
        from backend.services.engine.qlib_app.services.strategy_templates import get_template_by_id
    except Exception:
        get_template_by_id = None  # type: ignore

    for raw in candidates:
        key = _normalize_strategy_key(raw)
        if not key:
            continue
        if get_template_by_id:
            try:
                tpl = get_template_by_id(key)
                if tpl and getattr(tpl, "name", None):
                    return str(tpl.name)
            except Exception:
                pass
        fallback = namespaced_fallback_map.get(key.lower())
        if fallback:
            return fallback
    return None
