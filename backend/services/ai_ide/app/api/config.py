import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.ai_ide.app.settings import refresh_runtime_settings, settings

from .workspace import load_config, save_config

logger = logging.getLogger("AI-IDE-Config")
router = APIRouter()


class LLMConfig(BaseModel):
    qwen_api_key: str


@router.get("/llm")
async def get_llm_config():
    """获取 LLM 配置状态（脱敏）"""
    refresh_runtime_settings()
    config = load_config()
    key = config.get("qwen_api_key") or settings.api_key
    has_key = bool(key and key.strip())
    masked = f"{key[:3]}****{key[-4:]}" if has_key and len(key) > 8 else ""
    return {
        "success": True,
        "has_key": has_key,
        "masked_key": masked,
        "base_url": settings.base_url,
        "model": settings.model,
    }


@router.post("/llm")
async def save_llm_config(config: LLMConfig):
    """保存 LLM API Key 到统一配置 JSON (位于可写的 DATA_DIR)"""
    try:
        new_key = config.qwen_api_key.strip()
        if not new_key:
            raise HTTPException(status_code=400, detail="API Key 不能为空")

        # 1. 更新内存设置
        settings.api_key = new_key

        # 2. 写入全局配置 JSON (取代无法在安装目录下写入的 .env)
        save_config({"qwen_api_key": new_key})

        logger.info("Updated qwen_api_key in config.json")
        return {"success": True, "message": "配置已保存"}

    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
