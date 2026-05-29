from fastapi import APIRouter
from config.settings import settings

router = APIRouter(prefix="/api/v1/system", tags=["System"])

@router.get("/capabilities")
async def get_capabilities():
    """获取当前版本的系统能力与开关"""
    return settings.capabilities
