"""
Community App 统一路由导出。

将社区的所有子路由（帖子、评论、互动、上传、发现）聚合为单一 APIRouter，
供 api/main.py 一次注册，也为未来作为独立服务部署做好准备。
"""

from fastapi import APIRouter

from .routes import comments, explore, follows, interactions, posts, upload

router = APIRouter(prefix="/api/v1/community")

router.include_router(posts.router, tags=["Community-Posts"])
router.include_router(comments.router, tags=["Community-Comments"])
router.include_router(interactions.router, tags=["Community-Interactions"])
router.include_router(follows.router, tags=["Community-Follows"])
router.include_router(upload.router, tags=["Community-Upload"])
router.include_router(explore.router, tags=["Community-Explore"])
