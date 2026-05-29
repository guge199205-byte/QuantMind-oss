"""
User Center client for Community Service.

Lightweight httpx-based wrapper to fetch user summaries from the user-center
service with in-memory caching to avoid repeated calls.
"""

import os
import time
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.user_app.services.audit_service import AuditLogService
from backend.services.api.user_app.services.profile_service import ProfileService

# Configuration with sane defaults
USER_CENTER_CACHE_TTL = int(os.getenv("USER_CENTER_CACHE_TTL", "300"))

# Simple in-memory cache: user_id -> (expires_at, data)
_cache: dict[str, tuple] = {}
_stats: dict[str, int] = {"hit": 0, "miss": 0, "fail": 0}


async def fetch_user_summary(
    user_id: str, tenant_id: str = "default", fallback_name: str | None = None
) -> dict | None:
    """Fetch user summary via direct ProfileService call with caching."""
    now = time.time()
    cached = _cache.get(user_id)
    if cached and cached[0] > now:
        _stats["hit"] += 1
        return cached[1]
    _stats["miss"] += 1

    try:
        service = ProfileService()
        profile = await service.get_profile(user_id, tenant_id)
        if not profile:
            if fallback_name:
                summary = {
                    "id": user_id,
                    "name": fallback_name,
                    "avatar": None,
                    "bio": None,
                    "followers_count": 0,
                    "following_count": 0,
                    "posts_count": 0,
                    "likes_received": 0,
                }
                return summary
            _stats["fail"] += 1
            return None

        summary = {
            "id": profile.user_id,
            "name": profile.display_name or getattr(profile, "username_at_runtime", None) or f"QA_{user_id[:5]}",
            "avatar": profile.avatar_url,
            "bio": profile.bio,
            "followers_count": getattr(profile, "followers_count", 0),
            "following_count": getattr(profile, "following_count", 0),
            "posts_count": getattr(profile, "posts_count", 0),
            "likes_received": getattr(profile, "likes_received", 0),
        }
        _cache[user_id] = (now + USER_CENTER_CACHE_TTL, summary)
        return summary
    except Exception:
        if fallback_name:
            return {
                "id": user_id,
                "name": fallback_name,
                "avatar": None,
                "bio": None,
                "followers_count": 0,
                "following_count": 0,
                "posts_count": 0,
                "likes_received": 0,
            }
        _stats["fail"] += 1
        return None


async def record_activity(
    user_id: str,
    activity_type: str,
    activity_data: dict,
    tenant_id: str = "default",
    session: AsyncSession | None = None,
) -> bool:
    """Record user activity via direct AuditLogService call if session is provided."""
    if not session:
        # If no session provided, we can't record via DB service easily here
        # In a decoupled future, this might use an async task queue (e.g. Celery/RabbitMQ)
        return False

    try:
        audit_service = AuditLogService(session)
        await audit_service.log_action(
            user_id=user_id,
            tenant_id=tenant_id,
            action=activity_type,
            resource="community",
            description=f"Community activity: {activity_type}",
            request_data=activity_data,
            success=True,
        )
        return True
    except Exception:
        _stats["fail"] += 1
        return False


def clear_cache():
    _cache.clear()


def get_stats() -> dict[str, int]:
    return dict(_stats)
