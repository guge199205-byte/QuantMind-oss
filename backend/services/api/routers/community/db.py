"""Database helpers for Community service."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.community_app.models import (
    CommentRecord,
    InteractionRecord,
    PostRecord,
)
from backend.shared.database_manager_v2 import get_session as get_shared_session

# Re-exporting for compatibility with existing code
__all__ = ["PostRecord", "CommentRecord", "InteractionRecord", "get_session", "to_dict_post", "to_dict_comment"]


async def get_session(read_only: bool = False):
    """
    FastAPI dependency: yield an AsyncSession backed by shared DatabaseManager.
    Redirects to shared session manager.
    """
    async with get_shared_session(read_only=read_only) as session:
        yield session


def to_dict_post(db_obj: PostRecord) -> dict:
    return {
        "id": db_obj.id,
        "author_id": db_obj.author_id,
        "title": db_obj.title,
        "content": db_obj.content,
        "category": db_obj.category,
        "tags": db_obj.tags or [],
        "media": db_obj.media,
        "excerpt": db_obj.excerpt,
        "views": db_obj.views,
        "likes": db_obj.likes,
        "comments": db_obj.comments,
        "collections": db_obj.collections,
        "pinned": db_obj.pinned,
        "featured": db_obj.featured,
        "is_liked": False,
        "is_collected": False,
        "created_at": db_obj.created_at,
        "updated_at": db_obj.updated_at,
        "last_comment_at": db_obj.last_comment_at,
    }


def to_dict_comment(db_obj: CommentRecord) -> dict:
    return {
        "id": str(db_obj.id),
        "post_id": db_obj.post_id,
        "author_id": db_obj.author_id,
        "content": db_obj.content,
        "parent_id": str(db_obj.parent_id) if db_obj.parent_id else None,
        "reply_to_id": str(db_obj.reply_to_id) if db_obj.reply_to_id else None,
        "likes": db_obj.likes,
        "is_liked": False,
        "created_at": db_obj.created_at,
        "updated_at": db_obj.updated_at,
        "replies": [],
    }
