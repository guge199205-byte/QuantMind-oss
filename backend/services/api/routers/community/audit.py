"""Audit logging for community actions."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.community_app.models import AuditLogRecord
from backend.services.api.routers.community.auth import Principal

logger = logging.getLogger(__name__)


async def write_audit_log(
    session: AsyncSession,
    principal: Principal,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """
    写审计日志。
    注意：此函数依赖外层 session 生命周期提交；不会自己 commit。
    """
    ip = None
    ua = None
    if request is not None:
        ip = (request.client.host if request.client else None) or request.headers.get("x-forwarded-for")
        ua = request.headers.get("user-agent")

    rec = AuditLogRecord(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        ip=str(ip)[:64] if ip else None,
        user_agent=str(ua)[:256] if ua else None,
        meta=metadata or None,
        created_at=datetime.now(),
    )
    try:
        # 审计写入在 savepoint 中执行，失败时仅回滚审计子事务，避免污染主业务事务。
        async with session.begin_nested():
            session.add(rec)
            await session.flush([rec])
    except Exception as exc:
        logger.warning("Audit log persist failed, ignored: %s", exc)
