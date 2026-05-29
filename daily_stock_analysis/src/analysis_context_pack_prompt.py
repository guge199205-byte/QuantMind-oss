# -*- coding: utf-8 -*-
"""Prompt rendering for Issue #1389 AnalysisContextPack runtime summaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, Iterable, List, Optional


_BLOCK_LABELS_ZH = {
    "quote": "行情",
    "daily_bars": "日线",
    "technical": "技术",
    "chip": "筹码",
    "fundamentals": "基本面",
    "news": "新闻",
}

_BLOCK_LABELS_EN = {
    "quote": "quote",
    "daily_bars": "daily bars",
    "technical": "technical",
    "chip": "chip",
    "fundamentals": "fundamentals",
    "news": "news",
}

_SENSITIVE_MARKERS = (
    "api_key",
    "access_token",
    "refresh_token",
    "authorization",
    "webhook",
    "password",
    "cookie",
    "secret",
    "token",
    "sendkey",
    "license_key",
)


def format_analysis_context_pack_prompt_section(
    pack: Any,
    *,
    report_language: str = "zh",
) -> str:
    """Return a low-sensitivity prompt summary for an AnalysisContextPack.

    The renderer intentionally ignores item values. P3 consumes the pack as a
    runtime prompt signal only; full pack storage, API exposure, and quality
    scoring remain later phases.
    """
    payload = _pack_to_dict(pack)
    if not payload:
        return ""

    subject = payload.get("subject")
    blocks = payload.get("blocks")
    if not isinstance(subject, Mapping) or not isinstance(blocks, Mapping):
        return ""

    lang = "en" if str(report_language or "").lower() == "en" else "zh"
    return _format_en(payload) if lang == "en" else _format_zh(payload)


def _pack_to_dict(pack: Any) -> Dict[str, Any]:
    if pack is None:
        return {}
    if isinstance(pack, Mapping):
        return dict(pack)
    model_dump = getattr(pack, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump(mode="json")
        except TypeError:
            dumped = model_dump()
        except Exception:
            return {}
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _format_zh(payload: Dict[str, Any]) -> str:
    lines = ["", "## 分析上下文包摘要"]
    lines.extend(_subject_lines(payload, lang="zh"))
    block_lines = _block_lines(payload, lang="zh")
    if block_lines:
        lines.append("- 数据块状态：")
        lines.extend(f"  - {line}" for line in block_lines)
    metadata_lines = _metadata_lines(payload, lang="zh")
    if metadata_lines:
        lines.extend(metadata_lines)
    warnings = _list_strings(_nested(payload, "data_quality", "warnings"))
    if warnings:
        lines.append(f"- 数据质量提醒：{_join_text(warnings, lang='zh')}")
    return "\n".join(lines) + "\n"


def _format_en(payload: Dict[str, Any]) -> str:
    lines = ["", "## Analysis Context Pack Summary"]
    lines.extend(_subject_lines(payload, lang="en"))
    block_lines = _block_lines(payload, lang="en")
    if block_lines:
        lines.append("- Data block status:")
        lines.extend(f"  - {line}" for line in block_lines)
    metadata_lines = _metadata_lines(payload, lang="en")
    if metadata_lines:
        lines.extend(metadata_lines)
    warnings = _list_strings(_nested(payload, "data_quality", "warnings"))
    if warnings:
        lines.append(f"- Data quality notes: {_join_text(warnings, lang='en')}")
    return "\n".join(lines) + "\n"


def _subject_lines(payload: Dict[str, Any], *, lang: str) -> List[str]:
    subject = payload.get("subject") if isinstance(payload.get("subject"), Mapping) else {}
    code = _safe_text(subject.get("code"))
    name = _safe_text(subject.get("stock_name"))
    market = _safe_text(subject.get("market"))
    version = _safe_text(payload.get("pack_version"))

    if lang == "en":
        label = code or "unknown"
        if name:
            label += f" ({name})"
        line = f"- Subject: {label}"
        details = []
        if market:
            details.append(f"market={market}")
        if version:
            details.append(f"pack_version={version}")
        if details:
            line += f"; {', '.join(details)}"
        return [line]

    label = code or "未知标的"
    if name:
        label += f"（{name}）"
    line = f"- 标的：{label}"
    details = []
    if market:
        details.append(f"市场={market}")
    if version:
        details.append(f"pack_version={version}")
    if details:
        line += f"；{'，'.join(details)}"
    return [line]


def _block_lines(payload: Dict[str, Any], *, lang: str) -> List[str]:
    blocks = payload.get("blocks")
    if not isinstance(blocks, Mapping):
        return []

    labels = _BLOCK_LABELS_EN if lang == "en" else _BLOCK_LABELS_ZH
    ordered_keys = [key for key in _BLOCK_LABELS_ZH if key in blocks]
    ordered_keys.extend(key for key in blocks if key not in ordered_keys)

    lines: List[str] = []
    for key in ordered_keys:
        block = blocks.get(key)
        if not isinstance(block, Mapping):
            continue
        status = _safe_text(block.get("status")) or "unknown"
        label = labels.get(key, _safe_text(key))
        parts = [f"{label}: {status}"]

        source = _first_non_empty(
            block.get("source"),
            _first_item_field(block.get("items"), "source"),
        )
        if source:
            parts.append(f"source={source}")

        warnings = _list_strings(block.get("warnings"))
        if warnings:
            warning_label = "warnings" if lang == "en" else "告警"
            parts.append(f"{warning_label}={_join_text(warnings, lang=lang)}")

        reasons = _item_missing_reasons(block.get("items"))
        if reasons:
            reason_label = "missing_reason" if lang == "en" else "missing_reason"
            parts.append(f"{reason_label}={_join_text(reasons, lang=lang)}")

        lines.append("；".join(parts) if lang == "zh" else "; ".join(parts))
    return lines


def _metadata_lines(payload: Dict[str, Any], *, lang: str) -> List[str]:
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        return []
    news_count = metadata.get("news_result_count")
    if news_count is None:
        return []
    return [
        f"- News result count: {news_count}"
        if lang == "en"
        else f"- 新闻结果数：{news_count}"
    ]


def _first_item_field(items: Any, field: str) -> Optional[str]:
    if not isinstance(items, Mapping):
        return None
    for item in items.values():
        if not isinstance(item, Mapping):
            continue
        value = _safe_text(item.get(field))
        if value:
            return value
    return None


def _item_missing_reasons(items: Any) -> List[str]:
    if not isinstance(items, Mapping):
        return []
    reasons: List[str] = []
    for item in items.values():
        if not isinstance(item, Mapping):
            continue
        reason = _safe_text(item.get("missing_reason"))
        if reason and reason not in reasons:
            reasons.append(reason)
    return reasons[:3]


def _nested(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _list_strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    result: List[str] = []
    for item in value:
        text = _safe_text(item)
        if text and text not in result:
            result.append(text)
    return result[:5]


def _first_non_empty(*values: Any) -> Optional[str]:
    for value in values:
        text = _safe_text(value)
        if text:
            return text
    return None


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    lowered = text.lower()
    if any(marker in lowered for marker in _SENSITIVE_MARKERS):
        return "[REDACTED]"
    return text


def _join_text(values: Iterable[str], *, lang: str) -> str:
    separator = ", " if lang == "en" else "、"
    return separator.join(values)
