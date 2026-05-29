"""Content validation (P2)."""

from __future__ import annotations

import os
from typing import List

from fastapi import HTTPException


def _banned_words() -> list[str]:
    raw = os.getenv("COMMUNITY_BANNED_WORDS", "").strip()
    if not raw:
        return []
    words = [w.strip() for w in raw.split(",") if w.strip()]
    # de-dup while keeping order
    out: list[str] = []
    seen = set()
    for w in words:
        lw = w.lower()
        if lw in seen:
            continue
        seen.add(lw)
        out.append(w)
    return out


def validate_text(text: str, *, field: str) -> None:
    """
    简单敏感词拦截（逗号分隔，大小写不敏感）。
    """
    words = _banned_words()
    if not words:
        return
    hay = (text or "").lower()
    for w in words:
        if not w:
            continue
        if w.lower() in hay:
            raise HTTPException(status_code=400, detail=f"{field} contains banned word")
