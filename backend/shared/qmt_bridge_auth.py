"""
Shared QMT bridge session helpers used across services.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.trade.models.qmt_agent_binding import QMTAgentBinding
from backend.services.trade.models.qmt_agent_session import QMTAgentSession

SESSION_TTL_SECONDS = 3600
SESSION_REFRESH_THRESHOLD_SECONDS = 300


@dataclass
class BridgeSessionContext:
    session_id: str
    binding_id: str
    tenant_id: str
    user_id: str
    account_id: str
    client_fingerprint: str
    hostname: str | None
    client_version: str | None


def hash_bridge_token(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def generate_bridge_token() -> str:
    return f"qms_{secrets.token_urlsafe(32)}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_bridge_session(
    session: AsyncSession,
    binding: QMTAgentBinding,
) -> tuple[QMTAgentSession, str]:
    raw_token = generate_bridge_token()
    model = QMTAgentSession(
        binding_id=binding.id,
        tenant_id=binding.tenant_id,
        user_id=binding.user_id,
        token_hash=hash_bridge_token(raw_token),
        expires_at=utcnow() + timedelta(seconds=SESSION_TTL_SECONDS),
        revoked_at=None,
        last_used_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(model)
    await session.flush()
    return model, raw_token


async def revoke_session(session: AsyncSession, session_model: QMTAgentSession) -> None:
    session_model.revoked_at = utcnow()
    await session.flush()


async def verify_bridge_session_token(
    session: AsyncSession,
    raw_token: str,
) -> BridgeSessionContext | None:
    token_hash = hash_bridge_token(raw_token)
    result = await session.execute(
        select(QMTAgentSession, QMTAgentBinding)
        .join(QMTAgentBinding, QMTAgentBinding.id == QMTAgentSession.binding_id)
        .where(QMTAgentSession.token_hash == token_hash)
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None

    session_model, binding = row
    now = utcnow()
    if session_model.revoked_at is not None or session_model.expires_at <= now:
        return None
    if binding.status != "active":
        return None

    session_model.last_used_at = now
    binding.last_seen_at = now
    await session.flush()
    return BridgeSessionContext(
        session_id=session_model.id,
        binding_id=binding.id,
        tenant_id=binding.tenant_id,
        user_id=binding.user_id,
        account_id=binding.account_id,
        client_fingerprint=binding.client_fingerprint,
        hostname=binding.hostname,
        client_version=binding.client_version,
    )


async def refresh_bridge_session(
    session: AsyncSession,
    raw_token: str,
) -> tuple[BridgeSessionContext, str] | None:
    token_hash = hash_bridge_token(raw_token)
    result = await session.execute(
        select(QMTAgentSession, QMTAgentBinding)
        .join(QMTAgentBinding, QMTAgentBinding.id == QMTAgentSession.binding_id)
        .where(QMTAgentSession.token_hash == token_hash)
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None

    session_model, binding = row
    now = utcnow()
    if session_model.revoked_at is not None or session_model.expires_at <= now:
        return None

    await revoke_session(session, session_model)
    new_model, new_token = await create_bridge_session(session, binding)
    context = BridgeSessionContext(
        session_id=new_model.id,
        binding_id=binding.id,
        tenant_id=binding.tenant_id,
        user_id=binding.user_id,
        account_id=binding.account_id,
        client_fingerprint=binding.client_fingerprint,
        hostname=binding.hostname,
        client_version=binding.client_version,
    )
    return context, new_token

