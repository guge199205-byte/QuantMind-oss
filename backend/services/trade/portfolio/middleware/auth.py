"""
Auth middleware adapter for trade service.
Re-exports get_current_user_id using the trade service's own auth mechanism.
"""

from fastapi import Depends, HTTPException

from backend.services.trade.deps import AuthContext, get_auth_context


async def get_current_user_id(auth: AuthContext = Depends(get_auth_context)) -> str:
    """获取当前用户 ID (字符串类型，兼容 'admin' 等非数字ID)"""
    return auth.user_id


async def get_current_tenant_id(auth: AuthContext = Depends(get_auth_context)) -> str:
    tenant_id = str(auth.tenant_id or "").strip()
    return tenant_id or "default"
