"""Shared helpers for response shaping."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional


def strip_html_tags(html: str) -> str:
    """去除 HTML 标签，平铺为纯文本（避免词汇粘连）。"""
    if not html:
        return ""
    # 将标签替换为空格以防文字粘连
    clean = re.sub("<.*?>", " ", html)
    # 合并连续空格并去除首尾空格
    return " ".join(clean.split())


def author_block(user_id: str, summary: dict | None) -> dict:

    return {
        "id": user_id,
        "name": summary["name"] if summary else "匿名用户",
        "avatar": summary.get("avatar") if summary else None,
        "followers_count": summary.get("followers_count") if summary else None,
        "following_count": summary.get("following_count") if summary else None,
        "posts_count": summary.get("posts_count") if summary else None,
        "likes_received": summary.get("likes_received") if summary else None,
    }


def ts_ms(dt: datetime | None) -> int:
    return int(dt.timestamp() * 1000) if dt else 0
