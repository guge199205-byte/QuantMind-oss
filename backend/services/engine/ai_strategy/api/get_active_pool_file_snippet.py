"""
获取活跃股票池文件的API端点

添加到wizard.py的delete-pool-file之前
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

# 导入数据库相关
try:
    from backend.shared.database_pool import get_db
except ImportError:
    from shared.database_pool import get_db

# 导入模型
try:
    from backend.services.engine.ai_strategy.models.strategy import StockPoolFile
except ImportError:
    from models.strategy import StockPoolFile

logger = logging.getLogger(__name__)
router = APIRouter()


class GetActivePoolFileRequest(BaseModel):
    user_id: str


class GetActivePoolFileResponse(BaseModel):
    success: bool
    pool_file: dict[str, Any] | None = None
    error: str | None = None


@router.post("/get-active-pool-file", response_model=GetActivePoolFileResponse)
async def get_active_pool_file(body: GetActivePoolFileRequest):
    """获取用户当前活跃的股票池文件"""
    try:
        db = next(get_db())

        # 查询最新的活跃记录
        pool_file = (
            db.query(StockPoolFile)
            .filter(StockPoolFile.user_id == body.user_id, StockPoolFile.is_active == True)
            .order_by(StockPoolFile.created_at.desc())
            .first()
        )

        if pool_file:
            return GetActivePoolFileResponse(success=True, pool_file=pool_file.to_dict())
        else:
            return GetActivePoolFileResponse(success=True, pool_file=None)
    except Exception as e:
        logger.error(f"Get active pool file failed: {e}", exc_info=True)
        return GetActivePoolFileResponse(success=False, error=f"获取失败: {e}")
    finally:
        db.close()
