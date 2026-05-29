"""Utilities for cleaning and normalizing strategy metadata."""

from __future__ import annotations

from typing import List, Union
from collections.abc import Iterable, Sequence

_METADATA_SEPARATORS = ("\r\n", "\n", "；", ";", "、", "，", ",", "|", "/")
_BULLET_PREFIXES = ("-", "•", "*", "·")


def _split_candidate(value: str) -> list[str]:
    """Split a raw string into candidate metadata entries."""
    cleaned = value
    for sep in _METADATA_SEPARATORS:
        cleaned = cleaned.replace(sep, "|")
    candidates = [candidate.strip() for candidate in cleaned.split("|")]
    return [candidate for candidate in candidates if candidate]


def _strip_bullet(candidate: str) -> str:
    """Remove common bullet prefixes and leading numbering."""
    stripped = candidate.lstrip()

    # Remove ordered list like "1. "
    digits = []
    for ch in stripped:
        if ch.isdigit():
            digits.append(ch)
        else:
            break
    if digits and stripped[len(digits) :].startswith((".", ")")):
        stripped = stripped[len(digits) + 1 :].lstrip()

    # Remove bullet markers
    for prefix in _BULLET_PREFIXES:
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix) :].lstrip()

    return stripped.strip()


def _normalize_entry(entry: str) -> str:
    """Normalize whitespace within a single metadata entry."""
    normalized = " ".join(entry.split())
    return normalized


def normalize_text_list(value: str | Sequence[str] | None) -> list[str]:
    """Convert an arbitrary metadata field into a sanitized list of strings.

    Supports strings with various separators, sequences, and nested sequences.
    Removes duplicates (case-insensitive) while preserving order.
    """

    if value is None:
        return []

    candidates: Iterable = value if isinstance(value, (list, tuple, set)) else [value]

    normalized_items: list[str] = []
    for candidate in candidates:
        if candidate is None:
            continue

        if isinstance(candidate, (list, tuple, set)):
            inner_items = normalize_text_list(list(candidate))
            for item in inner_items:
                if item:
                    normalized_items.append(item)
            continue

        text = str(candidate).strip()
        if not text:
            continue

        for split_entry in (_split_candidate(text) if not isinstance(candidate, (list, tuple, set)) else [text]):
            entry = _strip_bullet(split_entry)
            if not entry:
                continue
            normalized_items.append(_normalize_entry(entry))

    deduped: list[str] = []
    seen = set()
    for item in normalized_items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped


def sanitize_note(value: str | Sequence[str] | None) -> str | None:
    """Normalize note fields into a single plain string."""
    if value is None:
        return None

    if isinstance(value, (list, tuple, set)):
        parts = [str(item).strip() for item in value if str(item).strip()]
        combined = "; ".join(parts)
    else:
        combined = str(value)

    condensed = " ".join(combined.split())
    return condensed or None
