"""Comment routes."""

from datetime import datetime
from functools import partial

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.community_app.models import CommentCreateIn, CommentUpdate

from ..audit import write_audit_log
from ..auth import Principal, get_principal, require_user
from ..db import CommentRecord, InteractionRecord, PostRecord
from ..deps import get_db_session, get_readonly_db_session
from ..user_center_client import fetch_user_summary
from ..validation import validate_text

router = APIRouter()
PAGE_QUERY = Query(1, ge=1)
PAGE_SIZE_QUERY = Query(20, alias="pageSize", ge=1, le=100)


@router.get("/posts/{post_id}/comments")
async def list_comments(
    post_id: int,
    page: int = PAGE_QUERY,
    page_size: int = PAGE_SIZE_QUERY,
    session: AsyncSession = Depends(get_readonly_db_session),
    principal: Principal = Depends(get_principal),
):
    """List comments for a post."""
    tenant_id = principal.tenant_id
    current_user = principal.user_id
    base = select(CommentRecord).where(CommentRecord.post_id == post_id, CommentRecord.tenant_id == tenant_id)
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one() or 0

    stmt = base.order_by(desc(CommentRecord.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    items = result.scalars().all()

    # Fetch comment likes for the current user
    user_liked_comment_ids = set()
    if current_user:
        comment_ids = [c.id for c in items]
        if comment_ids:
            inter_stmt = select(InteractionRecord).where(
                InteractionRecord.tenant_id == tenant_id,
                InteractionRecord.user_id == current_user,
                InteractionRecord.comment_id.in_(comment_ids),
                InteractionRecord.type == "like",
            )
            interactions = (await session.execute(inter_stmt)).scalars().all()
            for inter in interactions:
                user_liked_comment_ids.add(inter.comment_id)

    enriched = []
    for c in items:
        summary = await fetch_user_summary(c.author_id, tenant_id=tenant_id)
        author = {
            "id": c.author_id,
            "name": summary["name"] if summary else "匿名用户",
            "avatar": summary.get("avatar") if summary else None,
            "followers_count": summary.get("followers_count") if summary else None,
            "following_count": summary.get("following_count") if summary else None,
            "posts_count": summary.get("posts_count") if summary else None,
            "likes_received": summary.get("likes_received") if summary else None,
        }
        enriched.append(
            {
                "id": c.id,
                "postId": c.post_id,
                "content": c.content,
                "author": {
                    "id": author["id"],
                    "name": author["name"],
                    "avatar": author.get("avatar"),
                },
                "createdAt": int(c.created_at.timestamp() * 1000),
                "updatedAt": (int(c.updated_at.timestamp() * 1000) if c.updated_at else None),
                "likes": c.likes,
                "isLiked": c.id in user_liked_comment_ids,
                "parentId": c.parent_id,
                "replyTo": None,
                "replies": [],
                "repliesCount": 0,
                "isDeleted": False,
                "isOwner": current_user == c.author_id if current_user else False,
            }
        )

    return {
        "items": enriched,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": (total + page_size - 1) // page_size,
    }


@router.post("/posts/{post_id}/comments", status_code=201)
async def create_comment(
    post_id: int,
    request: Request,
    comment: CommentCreateIn,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    """Create a comment (requires authentication)."""
    tenant_id = principal.tenant_id
    current_user = principal.user_id or ""
    validate_text(comment.content, field="content")
    post_stmt = select(PostRecord).where(PostRecord.id == post_id, PostRecord.tenant_id == tenant_id)
    post = (await session.execute(post_stmt)).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    db_comment = CommentRecord(
        tenant_id=tenant_id,
        post_id=post_id,
        author_id=current_user,
        content=comment.content,
        parent_id=int(comment.parentId) if comment.parentId else None,
        reply_to_id=int(comment.replyToId) if comment.replyToId else None,
        created_at=datetime.now(),
    )
    session.add(db_comment)
    post.comments = (post.comments or 0) + 1
    post.last_comment_at = datetime.now()
    await session.flush()
    await session.refresh(db_comment)
    await write_audit_log(
        session,
        principal,
        action="comment.create",
        entity_type="comment",
        entity_id=str(db_comment.id),
        metadata={
            "post_id": post_id,
            "parentId": comment.parentId,
            "replyToId": comment.replyToId,
        },
        request=request,
    )
    summary = await fetch_user_summary(current_user, tenant_id=tenant_id)
    author = {
        "id": current_user,
        "name": summary["name"] if summary else "匿名用户",
        "avatar": summary.get("avatar") if summary else None,
    }
    return {
        "id": db_comment.id,
        "postId": db_comment.post_id,
        "content": db_comment.content,
        "author": author,
        "createdAt": int(db_comment.created_at.timestamp() * 1000),
        "updatedAt": (int(db_comment.updated_at.timestamp() * 1000) if db_comment.updated_at else None),
        "likes": db_comment.likes,
        "isLiked": False,
        "parentId": db_comment.parent_id,
        "replyTo": None,
        "replies": [],
        "repliesCount": 0,
        "isDeleted": False,
        "isOwner": True,
    }


@router.put("/comments/{comment_id}")
async def update_comment(
    comment_id: int,
    request: Request,
    comment: CommentUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    """Update a comment (requires ownership)."""
    tenant_id = principal.tenant_id
    current_user = principal.user_id or ""
    stmt = select(CommentRecord).where(CommentRecord.id == comment_id, CommentRecord.tenant_id == tenant_id)
    db_comment = (await session.execute(stmt)).scalar_one_or_none()
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if db_comment.author_id != current_user:
        raise HTTPException(status_code=403, detail="Permission denied")

    validate_text(comment.content, field="content")
    db_comment.content = comment.content
    db_comment.updated_at = datetime.now()

    await session.flush()
    await write_audit_log(
        session,
        principal,
        action="comment.update",
        entity_type="comment",
        entity_id=str(db_comment.id),
        metadata={"post_id": db_comment.post_id},
        request=request,
    )
    return {"success": True}


@router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    """Delete a comment (requires authentication and ownership)."""
    tenant_id = principal.tenant_id
    current_user = principal.user_id or ""
    stmt = select(CommentRecord).where(CommentRecord.id == int(comment_id), CommentRecord.tenant_id == tenant_id)
    db_comment = (await session.execute(stmt)).scalar_one_or_none()
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if db_comment.author_id != current_user:
        raise HTTPException(status_code=403, detail="Forbidden")
    post_stmt = select(PostRecord).where(PostRecord.id == db_comment.post_id, PostRecord.tenant_id == tenant_id)
    post = (await session.execute(post_stmt)).scalar_one_or_none()
    await session.delete(db_comment)
    if post and post.comments > 0:
        post.comments -= 1
    await write_audit_log(
        session,
        principal,
        action="comment.delete",
        entity_type="comment",
        entity_id=str(comment_id),
        metadata={"post_id": db_comment.post_id},
        request=request,
    )
    return {"message": "deleted"}
