"""Author follow/unfollow routes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import write_audit_log
from ..auth import Principal, get_principal, require_user
from ..deps import get_db_session

router = APIRouter()

_FOLLOW_TABLE_READY = False
_FOLLOW_TABLE_LOCK = asyncio.Lock()


async def _ensure_follow_table(session: AsyncSession) -> None:
    global _FOLLOW_TABLE_READY
    if _FOLLOW_TABLE_READY:
        return
    async with _FOLLOW_TABLE_LOCK:
        if _FOLLOW_TABLE_READY:
            return
        await session.execute(text("""
                CREATE TABLE IF NOT EXISTS community_author_follows (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id VARCHAR(64) NOT NULL,
                    follower_user_id VARCHAR(64) NOT NULL,
                    author_user_id VARCHAR(64) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_community_author_follows UNIQUE
                    (tenant_id, follower_user_id, author_user_id)
                )
                """))
        await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_comm_follow_tenant_author
                ON community_author_follows (tenant_id, author_user_id)
                """))
        await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_comm_follow_tenant_follower
                ON community_author_follows (tenant_id, follower_user_id)
                """))
        await session.flush()
        _FOLLOW_TABLE_READY = True


async def _count_followers(
    session: AsyncSession,
    tenant_id: str,
    author_id: str,
) -> int:
    result = await session.execute(
        text("""
            SELECT COUNT(1)
            FROM community_author_follows
            WHERE tenant_id = :tenant_id AND author_user_id = :author_id
            """),
        {"tenant_id": tenant_id, "author_id": author_id},
    )
    return int(result.scalar() or 0)


async def _is_following(
    session: AsyncSession,
    tenant_id: str,
    follower_id: str,
    author_id: str,
) -> bool:
    result = await session.execute(
        text("""
            SELECT 1
            FROM community_author_follows
            WHERE tenant_id = :tenant_id
              AND follower_user_id = :follower_id
              AND author_user_id = :author_id
            LIMIT 1
            """),
        {
            "tenant_id": tenant_id,
            "follower_id": follower_id,
            "author_id": author_id,
        },
    )
    return result.scalar() is not None


def _validate_author(author_id: str) -> str:
    value = (author_id or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Invalid author_id")
    return value


@router.get("/authors/{author_id}/follow-status")
async def get_follow_status(
    author_id: str,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_principal),
):
    tenant_id = principal.tenant_id
    author = _validate_author(author_id)
    await _ensure_follow_table(session)
    followers = await _count_followers(session, tenant_id, author)
    is_following = False
    if principal.user_id:
        is_following = await _is_following(
            session,
            tenant_id,
            principal.user_id,
            author,
        )
    return {
        "authorId": author,
        "isFollowing": is_following,
        "followers": followers,
    }


@router.post("/authors/{author_id}/follow")
async def follow_author(
    author_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    tenant_id = principal.tenant_id
    follower_id = principal.user_id or ""
    author = _validate_author(author_id)
    if follower_id == author:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    await _ensure_follow_table(session)
    result = await session.execute(
        text("""
            INSERT INTO community_author_follows
            (tenant_id, follower_user_id, author_user_id)
            VALUES (:tenant_id, :follower_id, :author_id)
            ON CONFLICT (tenant_id, follower_user_id, author_user_id) DO NOTHING
            """),
        {
            "tenant_id": tenant_id,
            "follower_id": follower_id,
            "author_id": author,
        },
    )
    changed = (result.rowcount or 0) > 0
    followers = await _count_followers(session, tenant_id, author)
    if changed:
        await write_audit_log(
            session,
            principal,
            action="interaction.follow_on",
            entity_type="user",
            entity_id=author,
            metadata={"author_id": author, "followers": followers},
            request=request,
        )
    return {"authorId": author, "isFollowing": True, "followers": followers}


@router.delete("/authors/{author_id}/follow")
async def unfollow_author(
    author_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    tenant_id = principal.tenant_id
    follower_id = principal.user_id or ""
    author = _validate_author(author_id)
    if follower_id == author:
        raise HTTPException(status_code=400, detail="Cannot unfollow yourself")

    await _ensure_follow_table(session)
    result = await session.execute(
        text("""
            DELETE FROM community_author_follows
            WHERE tenant_id = :tenant_id
              AND follower_user_id = :follower_id
              AND author_user_id = :author_id
            """),
        {
            "tenant_id": tenant_id,
            "follower_id": follower_id,
            "author_id": author,
        },
    )
    changed = (result.rowcount or 0) > 0
    followers = await _count_followers(session, tenant_id, author)
    if changed:
        await write_audit_log(
            session,
            principal,
            action="interaction.follow_off",
            entity_type="user",
            entity_id=author,
            metadata={"author_id": author, "followers": followers},
            request=request,
        )
    return {"authorId": author, "isFollowing": False, "followers": followers}
