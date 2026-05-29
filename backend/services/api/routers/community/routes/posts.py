"""Post routes."""

import logging
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.community_app.models import PostCreate, PostUpdate

from ..audit import write_audit_log
from ..auth import Principal, get_principal, require_user
from ..db import InteractionRecord, PostRecord, to_dict_post
from ..deps import get_db_session, get_readonly_db_session
from ..routes.explore import compute_hot_topics, compute_hot_users
from ..user_center_client import fetch_user_summary
from ..utils import author_block, strip_html_tags, ts_ms
from ..validation import validate_text

router = APIRouter()

PAGE_QUERY = Query(1, ge=1)
PAGE_SIZE_QUERY = Query(20, alias="pageSize", ge=1, le=100)
SORT_QUERY = Query("latest")


def _normalize_sort(sort: str) -> str:
    # Frontend uses Chinese sort labels; normalize for internal ordering.
    mapping = {
        "全部": "latest",
        "最新": "latest",
        "最热": "hottest",
        "热门": "hottest",
        "精华": "featured",
        "latest": "latest",
        "hottest": "hottest",
        "featured": "featured",
    }
    return mapping.get(sort, "latest")


_author_block = author_block
_ts = ts_ms


@router.get("/posts")
async def list_posts(
    page: int = PAGE_QUERY,
    page_size: int = PAGE_SIZE_QUERY,
    sort: str = SORT_QUERY,
    category: str | None = None,
    search: str | None = None,
    author_id: str | None = None,
    session: AsyncSession = Depends(get_readonly_db_session),
    principal: Principal = Depends(get_principal),
):
    """List posts with pagination and filtering."""
    sort = _normalize_sort(sort)
    tenant_id = principal.tenant_id
    base = select(PostRecord).where(PostRecord.tenant_id == tenant_id)
    if author_id:
        base = base.where(PostRecord.author_id == author_id)
    if category:
        base = base.where(PostRecord.category == category)
    if search:
        ilike = f"%{search}%"
        base = base.where(PostRecord.title.ilike(ilike) | PostRecord.content.ilike(ilike))

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one() or 0

    stmt = base
    if sort == "hottest":
        stmt = stmt.order_by(desc(PostRecord.likes))
    elif sort == "featured":
        stmt = stmt.order_by(desc(PostRecord.featured), desc(PostRecord.created_at))
    else:
        stmt = stmt.order_by(desc(PostRecord.created_at))

    result = await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    items = result.scalars().all()

    # Fetch interactions for the current user
    user_liked_post_ids = set()
    user_collected_post_ids = set()
    author_summaries = {}  # noqa: F841
    if principal.user_id:
        post_ids = [p.id for p in items]
        if post_ids:
            inter_stmt = select(InteractionRecord).where(
                InteractionRecord.tenant_id == tenant_id,
                InteractionRecord.user_id == principal.user_id,
                InteractionRecord.post_id.in_(post_ids),
            )
            interactions = (await session.execute(inter_stmt)).scalars().all()
            for inter in interactions:
                if inter.type == "like":
                    user_liked_post_ids.add(inter.post_id)
                elif inter.type == "collect":
                    user_collected_post_ids.add(inter.post_id)

    enriched_posts = []
    for db_post in items:
        data = to_dict_post(db_post)
        # normalize for frontend expectations
        normalized = {
            "id": data["id"],
            "title": data["title"],
            "excerpt": data["excerpt"],
            "content": data["content"],
            "category": data["category"],
            "tags": data["tags"],
            "views": data["views"],
            "comments": data["comments"],
            "likes": data["likes"],
            "collections": data["collections"],
            "featured": data["featured"],
            "pinned": data["pinned"],
            "thumbnail": None,
            "media": data["media"],
            "isLiked": db_post.id in user_liked_post_ids,
            "isCollected": db_post.id in user_collected_post_ids,
            "createdAt": _ts(data.get("created_at")),
            "lastCommentAt": _ts(data.get("last_comment_at")),
        }
        summary = await fetch_user_summary(
            db_post.author_id,
            tenant_id=tenant_id,
            fallback_name=principal.username if db_post.author_id == principal.user_id else None,
        )
        author = _author_block(db_post.author_id, summary)
        normalized["author"] = author["name"]
        normalized["authorAvatar"] = author.get("avatar")
        enriched_posts.append(normalized)

    return {
        "posts": enriched_posts,
        "pagination": {
            "current": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": (total + page_size - 1) // page_size,
        },
        "hotUsers": await compute_hot_users(session, tenant_id, limit=5),
        "hotTopics": await compute_hot_topics(session, tenant_id, limit=5),
        "promo": None,
    }


@router.get("/posts/recommendations")
async def get_recommendations(
    limit: int = Query(5, ge=1, le=20),
    session: AsyncSession = Depends(get_readonly_db_session),
    principal: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    """Get post recommendations (hot or featured)."""
    tenant_id = principal.tenant_id
    stmt = (
        select(PostRecord)
        .where(PostRecord.tenant_id == tenant_id)
        .order_by(desc(PostRecord.featured), desc(PostRecord.likes), desc(PostRecord.created_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()

    out = []
    for p in items:
        out.append(
            {
                "id": p.id,
                "title": p.title,
                "views": p.views,
                "comments": p.comments,
            }
        )
    return out


@router.get("/posts/{post_id}")
async def get_post(
    post_id: int,
    session: AsyncSession = Depends(get_readonly_db_session),
    principal: Principal = Depends(get_principal),
):
    """Get post detail by ID."""
    tenant_id = principal.tenant_id
    stmt = select(PostRecord).where(PostRecord.id == post_id, PostRecord.tenant_id == tenant_id)
    db_post = (await session.execute(stmt)).scalar_one_or_none()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Fetch interactions for the current user
    is_liked = False
    is_collected = False
    if principal.user_id:
        inter_stmt = select(InteractionRecord).where(
            InteractionRecord.tenant_id == tenant_id,
            InteractionRecord.user_id == principal.user_id,
            InteractionRecord.post_id == post_id,
        )
        interactions = (await session.execute(inter_stmt)).scalars().all()
        for inter in interactions:
            if inter.type == "like":
                is_liked = True
            elif inter.type == "collect":
                is_collected = True

    data = to_dict_post(db_post)
    summary = await fetch_user_summary(
        db_post.author_id,
        tenant_id=tenant_id,
        fallback_name=principal.username if db_post.author_id == principal.user_id else None,
    )
    author = _author_block(db_post.author_id, summary)
    return {
        "id": data["id"],
        "title": data["title"],
        "excerpt": data["excerpt"],
        "content": data["content"],
        "category": data["category"],
        "tags": data["tags"],
        "views": data["views"],
        "comments": data["comments"],
        "likes": data["likes"],
        "collections": data["collections"],
        "featured": data["featured"],
        "pinned": data["pinned"],
        "thumbnail": None,
        "media": data["media"],
        "isLiked": is_liked,
        "isCollected": is_collected,
        "createdAt": _ts(data.get("created_at")),
        "lastCommentAt": _ts(data.get("last_comment_at")),
        "author": author["name"],
        "authorAvatar": author.get("avatar"),
        "authorInfo": author,
    }


@router.post("/posts", status_code=201)
async def create_post(
    request: Request,
    post: PostCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    """Create a new post (requires authentication)."""
    try:
        tenant_id = principal.tenant_id
        current_user = principal.user_id or ""
        validate_text(post.title, field="title")
        validate_text(post.content, field="content")

        db_post = PostRecord(
            tenant_id=tenant_id,
            author_id=current_user,
            title=post.title,
            content=post.content,
            category=post.category,
            tags=post.tags,
            media=post.media,
            excerpt=(
                (strip_html_tags(post.content)[:140] + "...")
                if len(strip_html_tags(post.content)) > 140
                else strip_html_tags(post.content)
            ),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            last_comment_at=datetime.now(),
        )
        session.add(db_post)
        await write_audit_log(
            session,
            principal,
            action="post.create",
            entity_type="post",
            entity_id=str(db_post.id),
            metadata={"category": post.category},
            request=request,
        )
        summary = await fetch_user_summary(current_user, tenant_id=tenant_id, fallback_name=principal.username)
        author = _author_block(current_user, summary)

        await session.commit()
        await session.refresh(db_post)
        data = to_dict_post(db_post)
        return {
            "id": data["id"],
            "title": data["title"],
            "excerpt": data["excerpt"],
            "content": data["content"],
            "category": data["category"],
            "tags": data["tags"],
            "views": data["views"],
            "comments": data["comments"],
            "likes": data["likes"],
            "collections": data["collections"],
            "featured": data["featured"],
            "pinned": data["pinned"],
            "thumbnail": None,
            "media": data["media"],
            "isLiked": False,
            "isCollected": False,
            "createdAt": _ts(data.get("created_at")),
            "lastCommentAt": _ts(data.get("last_comment_at")),
            "author": author["name"],
            "authorAvatar": author.get("avatar"),
            "authorInfo": author,
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Error creating post: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/posts/{post_id}")
async def update_post(
    post_id: int,
    request: Request,
    post: PostUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    """Update a post (requires authentication and ownership)."""
    tenant_id = principal.tenant_id
    current_user = principal.user_id or ""
    stmt = select(PostRecord).where(PostRecord.id == post_id, PostRecord.tenant_id == tenant_id)
    db_post = (await session.execute(stmt)).scalar_one_or_none()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    if db_post.author_id != current_user:
        raise HTTPException(status_code=403, detail="Forbidden")

    for k, v in post.model_dump(exclude_unset=True).items():
        if v is not None:
            if k in ("title", "content"):
                validate_text(str(v), field=k)
            setattr(db_post, k, v)
    db_post.updated_at = datetime.now()
    await session.flush()
    await session.refresh(db_post)
    await write_audit_log(
        session,
        principal,
        action="post.update",
        entity_type="post",
        entity_id=str(db_post.id),
        metadata={"fields": list(post.model_dump(exclude_unset=True).keys())},
        request=request,
    )
    summary = await fetch_user_summary(
        db_post.author_id,
        tenant_id=tenant_id,
        fallback_name=principal.username if db_post.author_id == principal.user_id else None,
    )
    author = _author_block(db_post.author_id, summary)
    data = to_dict_post(db_post)
    return {
        "id": data["id"],
        "title": data["title"],
        "excerpt": data["excerpt"],
        "content": data["content"],
        "category": data["category"],
        "tags": data["tags"],
        "views": data["views"],
        "comments": data["comments"],
        "likes": data["likes"],
        "collections": data["collections"],
        "featured": data["featured"],
        "pinned": data["pinned"],
        "thumbnail": None,
        "media": data["media"],
        "isLiked": False,
        "isCollected": False,
        "createdAt": _ts(data.get("created_at")),
        "lastCommentAt": _ts(data.get("last_comment_at")),
        "author": author["name"],
        "authorAvatar": author.get("avatar"),
        "authorInfo": author,
    }


@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(require_user),
):
    """Delete a post (requires authentication and ownership)."""
    tenant_id = principal.tenant_id
    current_user = principal.user_id or ""
    stmt = select(PostRecord).where(PostRecord.id == post_id, PostRecord.tenant_id == tenant_id)
    db_post = (await session.execute(stmt)).scalar_one_or_none()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    if db_post.author_id != current_user:
        raise HTTPException(status_code=403, detail="Forbidden")
    await session.delete(db_post)
    await write_audit_log(
        session,
        principal,
        action="post.delete",
        entity_type="post",
        entity_id=str(post_id),
        request=request,
    )
    return {"message": "deleted"}
