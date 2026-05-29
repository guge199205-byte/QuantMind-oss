"""Interaction routes (likes, collections)."""

from __future__ import annotations

from functools import partial
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import write_audit_log
from ..auth import Principal, require_user
from ..db import CommentRecord, InteractionRecord, PostRecord
from ..deps import get_db_session
from ..user_center_client import record_activity

router = APIRouter()


def _get_user_id(auth_user: str | None, x_user_id: str | None) -> str:
    # Prefer JWT user; fallback to header for backward compatibility
    return auth_user or x_user_id or ""


async def _toggle_interaction(
    session: AsyncSession,
    tenant_id: str,
    user_id: str,
    action: str,
    post_id: int | None = None,
    comment_id: int | None = None,
    force_state: bool | None = None,
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    target_obj = None
    if post_id:
        post_stmt = select(PostRecord).where(PostRecord.id == post_id, PostRecord.tenant_id == tenant_id)
        target_obj = (await session.execute(post_stmt)).scalar_one_or_none()
        if not target_obj:
            raise HTTPException(status_code=404, detail="Post not found")
    elif comment_id:
        comment_stmt = select(CommentRecord).where(CommentRecord.id == comment_id, CommentRecord.tenant_id == tenant_id)
        target_obj = (await session.execute(comment_stmt)).scalar_one_or_none()
        if not target_obj:
            raise HTTPException(status_code=404, detail="Comment not found")
    else:
        raise HTTPException(status_code=400, detail="Missing post_id or comment_id")

    stmt = select(InteractionRecord).where(
        and_(
            InteractionRecord.tenant_id == tenant_id,
            InteractionRecord.post_id == post_id,
            InteractionRecord.comment_id == comment_id,
            InteractionRecord.user_id == user_id,
            InteractionRecord.type == action,
        )
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()

    def get_count():
        if action == "like":
            return target_obj.likes
        return getattr(target_obj, "collections", 0)

    if existing:
        if force_state is True:
            return True, get_count(), False
        if force_state is False or force_state is None:
            await session.delete(existing)
            if action == "like" and target_obj.likes > 0:
                target_obj.likes -= 1
            if action == "collect" and hasattr(target_obj, "collections") and target_obj.collections > 0:
                target_obj.collections -= 1
            await session.flush()
            return False, get_count(), True

    # not existing
    if force_state is False:
        return False, get_count(), False

    # create new
    session.add(
        InteractionRecord(
            tenant_id=tenant_id,
            post_id=post_id,
            comment_id=comment_id,
            user_id=user_id,
            type=action,
        )
    )
    if action == "like":
        target_obj.likes += 1
    if action == "collect" and hasattr(target_obj, "collections"):
        target_obj.collections += 1
    await session.flush()
    return True, get_count(), True


@router.post("/posts/{post_id}/like")
async def like_post(
    post_id: int,
    request: Request,
    x_user_id: str | None = Header(default=None, convert_underscores=False),
    body: dict | None = None,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    """Like a post (requires authentication)."""
    tenant_id = principal.tenant_id
    user_id = _get_user_id(principal.user_id, x_user_id)
    desired = None
    if body and "isLiked" in body:
        desired = bool(body["isLiked"])
    liked, likes, changed = await _toggle_interaction(
        session, tenant_id, user_id, "like", post_id=post_id, force_state=desired
    )
    if changed:
        await write_audit_log(
            session,
            principal,
            action="interaction.like_on" if liked else "interaction.like_off",
            entity_type="post",
            entity_id=str(post_id),
            metadata={
                "post_id": post_id,
                "isLiked": liked,
                "likes": likes,
                "desired": desired,
            },
            request=request,
        )
    if changed and liked:
        await record_activity(
            user_id, "like_post", {"post_id": post_id, "action": "like"}, tenant_id=tenant_id, session=session
        )
    return {"isLiked": liked, "likes": likes}


@router.delete("/posts/{post_id}/like")
async def unlike_post(
    post_id: int,
    request: Request,
    x_user_id: str | None = Header(default=None, convert_underscores=False),
    body: dict | None = None,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    """Unlike a post (requires authentication)."""
    tenant_id = principal.tenant_id
    user_id = _get_user_id(principal.user_id, x_user_id)
    desired = False
    if body and "isLiked" in body:
        desired = bool(body["isLiked"])
    liked, likes, changed = await _toggle_interaction(
        session, tenant_id, user_id, "like", post_id=post_id, force_state=desired
    )
    if changed:
        await write_audit_log(
            session,
            principal,
            action="interaction.like_on" if liked else "interaction.like_off",
            entity_type="post",
            entity_id=str(post_id),
            metadata={
                "post_id": post_id,
                "isLiked": liked,
                "likes": likes,
                "desired": desired,
            },
            request=request,
        )
    if changed and not liked:
        await record_activity(
            user_id, "unlike_post", {"post_id": post_id, "action": "unlike"}, tenant_id=tenant_id, session=session
        )
    return {"isLiked": False, "likes": likes}


@router.post("/posts/{post_id}/collect")
async def collect_post(
    post_id: int,
    request: Request,
    x_user_id: str | None = Header(default=None, convert_underscores=False),
    body: dict | None = None,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    """Collect a post (requires authentication)."""
    tenant_id = principal.tenant_id
    user_id = _get_user_id(principal.user_id, x_user_id)
    desired = None
    if body and "isCollected" in body:
        desired = bool(body["isCollected"])
    collected, collections, changed = await _toggle_interaction(
        session, tenant_id, user_id, "collect", post_id=post_id, force_state=desired
    )
    if changed:
        await write_audit_log(
            session,
            principal,
            action="interaction.collect_on" if collected else "interaction.collect_off",
            entity_type="post",
            entity_id=str(post_id),
            metadata={
                "post_id": post_id,
                "isCollected": collected,
                "collections": collections,
                "desired": desired,
            },
            request=request,
        )
    if changed and collected:
        await record_activity(
            user_id, "collect_post", {"post_id": post_id, "action": "collect"}, tenant_id=tenant_id, session=session
        )
    return {"isCollected": collected, "collections": collections}


@router.delete("/posts/{post_id}/collect")
async def uncollect_post(
    post_id: int,
    request: Request,
    x_user_id: str | None = Header(default=None, convert_underscores=False),
    body: dict | None = None,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    """Uncollect a post (requires authentication)."""
    tenant_id = principal.tenant_id
    user_id = _get_user_id(principal.user_id, x_user_id)
    desired = False
    if body and "isCollected" in body:
        desired = bool(body["isCollected"])
    collected, collections, changed = await _toggle_interaction(
        session, tenant_id, user_id, "collect", post_id=post_id, force_state=desired
    )
    if changed:
        await write_audit_log(
            session,
            principal,
            action="interaction.collect_on" if collected else "interaction.collect_off",
            entity_type="post",
            entity_id=str(post_id),
            metadata={
                "post_id": post_id,
                "isCollected": collected,
                "collections": collections,
                "desired": desired,
            },
            request=request,
        )
    if changed and not collected:
        await record_activity(
            user_id, "uncollect_post", {"post_id": post_id, "action": "uncollect"}, tenant_id=tenant_id, session=session
        )
    return {"isCollected": False, "collections": collections}


@router.post("/comments/{comment_id}/like")
async def like_comment(
    comment_id: int,
    request: Request,
    x_user_id: str | None = Header(default=None, convert_underscores=False),
    body: dict | None = None,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    """Like a comment (requires authentication)."""
    tenant_id = principal.tenant_id
    user_id = _get_user_id(principal.user_id, x_user_id)
    desired = None
    if body and "isLiked" in body:
        desired = bool(body["isLiked"])
    liked, likes, changed = await _toggle_interaction(
        session, tenant_id, user_id, "like", comment_id=comment_id, force_state=desired
    )
    if changed:
        await write_audit_log(
            session,
            principal,
            action=("interaction.comment_like_on" if liked else "interaction.comment_like_off"),
            entity_type="comment",
            entity_id=str(comment_id),
            metadata={"comment_id": comment_id, "isLiked": liked, "likes": likes},
            request=request,
        )
    return {"isLiked": liked, "likes": likes}


@router.delete("/comments/{comment_id}/like")
async def unlike_comment(
    comment_id: int,
    request: Request,
    x_user_id: str | None = Header(default=None, convert_underscores=False),
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    """Unlike a comment (requires authentication)."""
    tenant_id = principal.tenant_id
    user_id = _get_user_id(principal.user_id, x_user_id)
    liked, likes, changed = await _toggle_interaction(
        session, tenant_id, user_id, "like", comment_id=comment_id, force_state=False
    )
    if changed:
        await write_audit_log(
            session,
            principal,
            action="interaction.comment_like_off",
            entity_type="comment",
            entity_id=str(comment_id),
            metadata={"comment_id": comment_id, "isLiked": False, "likes": likes},
            request=request,
        )
    return {"isLiked": False, "likes": likes}
