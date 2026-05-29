"""AI 策略向导 - 股票池统一状态管理 (Refactoring Phase A)

实现 SSOT (Single Source of Truth) 模型：
- WorkingPool: 缓存中的当前编辑池
- SavedPool: 数据库中的版本化历史
- ActivePool: 当前策略绑定的池子
"""

import logging
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from sqlalchemy import text

from backend.shared.redis_sentinel_client import get_redis_sentinel_client
from ..schemas.stock_pool import (
    PoolItem, 
    WorkingPool, 
    SaveWorkingPoolRequest,
    SavePoolFileResponse,
    ListPoolFilesResponse,
    GetActivePoolFileResponse
)

try:
    from backend.shared.database_pool import get_db
except ImportError:
    from shared.database_pool import get_db

from ...models.stock_pool_file import StockPoolFile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pool", tags=["strategy-pool-v2"])

WORKING_POOL_PREFIX = "quantmind:strategy:working_pool:"

def _get_working_key(user_id: str) -> str:
    return f"{WORKING_POOL_PREFIX}{user_id}"

@router.get("/working", response_model=WorkingPool)
async def get_working_pool(request: Request):
    """获取当前编辑中的股票池"""
    user_id = getattr(request.state, "user", {}).get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    redis = get_redis_sentinel_client()
    data = redis.get(_get_working_key(user_id))
    
    if not data:
        # 如果缓存没有，返回空池
        return WorkingPool(user_id=user_id, items=[])
    
    try:
        pool_data = json.loads(data)
        return WorkingPool(**pool_data)
    except Exception as e:
        logger.error(f"Failed to parse working pool for user {user_id}: {e}")
        return WorkingPool(user_id=user_id, items=[])

@router.post("/working")
async def save_working_pool(body: SaveWorkingPoolRequest, request: Request):
    """覆盖更新当前编辑中的股票池"""
    user_id = getattr(request.state, "user", {}).get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    pool = WorkingPool(user_id=user_id, items=body.items)
    redis = get_redis_sentinel_client()
    
    success = redis.set(
        _get_working_key(user_id), 
        json.dumps(pool.dict(), ensure_ascii=False).encode("utf-8"),
        ex=86400 * 7 # 缓存7天
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save working pool to cache")
    
    return {"success": True, "updated_at": pool.updated_at}

@router.get("/versions", response_model=ListPoolFilesResponse)
async def list_pool_versions(request: Request, limit: int = 50):
    """获取用户保存的所有股票池版本"""
    from .storage import list_pool_files as legacy_list
    from ..schemas.stock_pool import ListPoolFilesRequest
    
    user_id = getattr(request.state, "user", {}).get("user_id")
    return await legacy_list(ListPoolFilesRequest(user_id=user_id, limit=limit))

@router.post("/versions/save")
async def save_version_from_working(request: Request, pool_name: str):
    """从当前 WorkingPool 生成一个持久化版本"""
    user_id = getattr(request.state, "user", {}).get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    # 1. 获取 WorkingPool
    redis = get_redis_sentinel_client()
    data = redis.get(_get_working_key(user_id))
    if not data:
        raise HTTPException(status_code=400, detail="Working pool is empty, nothing to save")
    
    pool_data = json.loads(data)
    items = pool_data.get("items", [])
    
    # 2. 调用旧版保存逻辑 (存入 DB/COS)
    from .storage import save_pool_file as legacy_save
    from ..schemas.stock_pool import SavePoolFileRequest
    
    # 转换格式为旧版期待的结构
    legacy_items = [{"symbol": item["symbol"], "name": item.get("name", "")} for item in items]
    
    res = await legacy_save(SavePoolFileRequest(
        user_id=user_id,
        pool_name=pool_name,
        format="txt",
        pool=legacy_items
    ), request)
    
    return res

@router.post("/versions/{file_key:path}/activate")
async def activate_version(file_key: str, request: Request):
    """激活特定版本的股票池作为当前策略池"""
    user_id = getattr(request.state, "user", {}).get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    # 这里逻辑是更新 DB 中的 is_active 字段
    # 旧版 save_pool_file 已经处理了 is_active 的切换
    # 但如果用户是选择一个已有的版本激活，需要一个独立的更新逻辑
    try:
        with get_db() as db:
            # 先取消激活该用户的所有池子
            db.execute(text(
                "UPDATE stock_pool_files SET is_active = false WHERE user_id = :user_id"
            ), {"user_id": user_id})
            
            # 激活指定的池子
            res = db.execute(text(
                "UPDATE stock_pool_files SET is_active = true WHERE user_id = :user_id AND file_key = :file_key"
            ), {"user_id": user_id, "file_key": file_key})
            
            db.commit()
            
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="Pool version not found")
                
        return {"success": True, "activated_key": file_key}
    except Exception as e:
        logger.error(f"Failed to activate pool {file_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active", response_model=GetActivePoolFileResponse)
async def get_active_pool(request: Request):
    """获取当前策略流程绑定的激活池"""
    # 逻辑复用旧版的 get_active_pool_file 但路径统一
    from .storage import get_active_pool_file as legacy_get_active
    from ..schemas.stock_pool import GetActivePoolFileRequest
    
    user_id = getattr(request.state, "user", {}).get("user_id")
    return await legacy_get_active(GetActivePoolFileRequest(user_id=user_id), request)

# 后续阶段将在此添加 versions 相关逻辑
