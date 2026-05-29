import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.shared.strategy_storage import get_strategy_storage_service
from backend.shared.utils import normalize_user_id

logger = logging.getLogger(__name__)
router = APIRouter()

class CreateItemRequest(BaseModel):
    name: str
    dir: str | None = None

class SaveRequest(BaseModel):
    content: str

def _get_user_id(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return str(user.get("user_id") or user.get("sub"))

@router.get("/list")
async def list_files(request: Request, path: str = ""):
    """
    列出策略工作区。在云端模式下，每个策略记录对应一个文件。
    """
    try:
        user_id = _get_user_id(request)
        svc = get_strategy_storage_service()

        # 获取用户的所有策略
        items = svc.list(user_id=user_id)

        # 将策略项映射为 IDE 文件项
        ide_items = []
        for s in items:
            ide_items.append({
                "id": s["id"],
                "name": s["name"] + ".py" if not s["name"].endswith(".py") else s["name"],
                "path": s["id"], # 在云端，路径即 ID
                "type": "file",
                "size": 0, # TODO: 优化获取大小
                "last_modified": s.get("updated_at"),
            })

        return {
            "items": ide_items,
            "base": "cloud_workspace",
            "parent": None,
            "current": "",
        }
    except Exception as e:
        logger.error(f"Failed to list cloud files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create/file")
async def create_file(request: Request, item: CreateItemRequest):
    try:
        user_id = _get_user_id(request)
        svc = get_strategy_storage_service()

        # 去掉 .py 后缀作为策略名
        name = item.name
        if name.endswith(".py"):
            name = name[:-3]

        res = await svc.save(
            user_id=user_id,
            name=name,
            code="# New Strategy\n",
            metadata={"status": "DRAFT", "description": "Created via Cloud IDE"}
        )
        return {"status": "success", "id": res["id"]}
    except Exception as e:
        logger.error(f"Failed to create cloud file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{file_id:path}")
async def get_content(request: Request, file_id: str):
    try:
        user_id = _get_user_id(request)
        svc = get_strategy_storage_service()

        # 兼容带 .py 的请求
        sid = file_id
        if sid.endswith(".py") and "-" in sid: # UUID-like
             sid = sid[:-3]

        strategy = await svc.get(sid, user_id=user_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

        return {"content": strategy.get("code", "")}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get strategy content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{file_id:path}")
async def save_content(request: Request, file_id: str, item: SaveRequest):
    try:
        user_id = _get_user_id(request)
        svc = get_strategy_storage_service()

        sid = file_id
        if sid.endswith(".py"):
            sid = sid[:-3]

        # 针对 422 调试：记录请求详情
        if not item.content:
             logger.warning(f"Empty content received for sid={sid}")

        # 先获取元数据以保留
        try:
            existing = await svc.get(sid, user_id=user_id)
        except Exception as e:
            logger.error(f"Failed to fetch strategy {sid} before save: {e}")
            raise HTTPException(status_code=404, detail="Strategy not found")

        if not existing:
             raise HTTPException(status_code=404, detail="Strategy not found")

        await svc.save(
            user_id=user_id,
            strategy_id=sid,
            name=existing["name"],
            code=item.content,
            metadata={
                "description": existing.get("description"),
                "tags": existing.get("tags"),
                "parameters": existing.get("parameters"),
                "is_verified": existing.get("is_verified", False)
            }
        )
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save strategy content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{file_id:path}")
async def delete_item(request: Request, file_id: str):
    try:
        user_id = _get_user_id(request)
        svc = get_strategy_storage_service()

        sid = file_id
        if sid.endswith(".py"):
            sid = sid[:-3]

        success = await svc.delete(sid, user_id=user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))
