"""Explore endpoints (hot users/topics, search)."""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import partial
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import Principal, get_principal
from ..db import (
    InteractionRecord,
    PostRecord,
    to_dict_post,
)
from ..deps import get_readonly_db_session
from ..user_center_client import fetch_user_summary
from ..utils import author_block as _author_block
from ..utils import ts_ms as _ts

router = APIRouter()

PAGE_QUERY = Query(1, ge=1)
PAGE_SIZE_QUERY = Query(20, alias="pageSize", ge=1, le=100)


async def compute_hot_users(session: AsyncSession, tenant_id: str, *, limit: int = 5) -> list[dict[str, Any]]:
    now = datetime.now()
    win = now - timedelta(days=7)
    prev = win - timedelta(days=7)

    score_expr = func.sum(PostRecord.likes * 2 + PostRecord.comments * 1 + 5).label("score")
    s7 = (
        select(PostRecord.author_id, score_expr)
        .where(PostRecord.tenant_id == tenant_id, PostRecord.created_at >= win)
        .group_by(PostRecord.author_id)
    ).subquery("s7")

    s_prev = (
        select(
            PostRecord.author_id,
            func.sum(PostRecord.likes * 2 + PostRecord.comments * 1 + 5).label("score"),
        )
        .where(
            PostRecord.tenant_id == tenant_id,
            PostRecord.created_at >= prev,
            PostRecord.created_at < win,
        )
        .group_by(PostRecord.author_id)
        .subquery("s_prev")
    )

    stmt = (
        select(s7.c.author_id, s7.c.score, s_prev.c.score)
        .select_from(s7)
        .outerjoin(s_prev, s_prev.c.author_id == s7.c.author_id)
        .order_by(desc(s7.c.score))
        .limit(limit)
    )

    rows = (await session.execute(stmt)).all()
    out: list[dict[str, Any]] = []
    for author_id, score, prev_score in rows:
        summary = await fetch_user_summary(str(author_id), tenant_id=tenant_id)
        author = _author_block(str(author_id), summary)
        out.append(
            {
                "id": str(author_id),
                "name": author["name"],
                "avatar": author.get("avatar"),
                "score": int(score or 0),
                "trend": "up" if (score or 0) >= (prev_score or 0) else "down",
            }
        )
    return out


async def compute_hot_topics(session: AsyncSession, tenant_id: str, *, limit: int = 5) -> list[dict[str, Any]]:
    stmt = (
        select(PostRecord.category, func.count().label("cnt"))
        .where(PostRecord.tenant_id == tenant_id)
        .group_by(PostRecord.category)
        .order_by(desc(func.count()))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [{"name": str(cat or ""), "count": int(cnt)} for (cat, cnt) in rows]


@router.get("/hot-users")
async def hot_users(
    limit: int = Query(5, ge=1, le=20),
    session: AsyncSession = Depends(get_readonly_db_session),
    principal: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    """
    返回活跃用户列表（按 tenant_id 隔离）。

    返回结构对齐前端：[{id, name, avatar, score, trend}]
    """
    return await compute_hot_users(session, principal.tenant_id, limit=limit)


@router.get("/hot-topics")
async def hot_topics(
    limit: int = Query(5, ge=1, le=20),
    session: AsyncSession = Depends(get_readonly_db_session),
    principal: Principal = Depends(get_principal),
) -> list[dict[str, Any]]:
    """
    返回热门话题（当前以 category 作为话题维度，后续可升级为 tags 聚合）。

    返回结构对齐前端：[{name, count}]
    """
    return await compute_hot_topics(session, principal.tenant_id, limit=limit)


@router.get("/search")
async def search_posts(
    q: str = Query("", max_length=200),
    page: int = PAGE_QUERY,
    page_size: int = PAGE_SIZE_QUERY,
    session: AsyncSession = Depends(get_readonly_db_session),
    principal: Principal = Depends(get_principal),
):
    """
    简易搜索（title/content ilike），按 tenant_id 隔离。
    返回结构对齐 posts 列表的基本字段 + pagination。
    """
    tenant_id = principal.tenant_id
    ilike = f"%{q}%"
    base = select(PostRecord).where(PostRecord.tenant_id == tenant_id)
    if q:
        base = base.where(PostRecord.title.ilike(ilike) | PostRecord.content.ilike(ilike))

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one() or 0

    stmt = base.order_by(desc(PostRecord.created_at)).offset((page - 1) * page_size).limit(page_size)
    items = (await session.execute(stmt)).scalars().all()

    # Fetch interactions for the current user
    user_liked_post_ids = set()
    user_collected_post_ids = set()
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

    posts: list[dict[str, Any]] = []
    for db_post in items:
        data = to_dict_post(db_post)
        summary = await fetch_user_summary(db_post.author_id, tenant_id=tenant_id)
        author = _author_block(db_post.author_id, summary)
        posts.append(
            {
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
                "author": author["name"],
                "authorAvatar": author.get("avatar"),
            }
        )

    return {
        "posts": posts,
        "pagination": {
            "current": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": (total + page_size - 1) // page_size,
        },
    }
