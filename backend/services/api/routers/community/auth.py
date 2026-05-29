"""Minimal JWT auth utilities for Community service.

统一使用 backend.shared.auth.decode_jwt_token，密钥从环境变量动态读取。
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.shared.auth import decode_jwt_token

security_scheme = HTTPBearer(auto_error=False)


def decode_token(token: str) -> dict | None:
    """Decode JWT; return payload or None if invalid."""
    try:
        return decode_jwt_token(token)
    except HTTPException:
        return None


class Principal(BaseModel):
    tenant_id: str
    user_id: str | None = None
    username: str | None = None
    roles: list[str] = []


def get_principal(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
    x_tenant_id: str | None = Header(default=None, alias="x-tenant-id"),
) -> Principal:
    """
    获取当前请求的租户与用户信息。

    - tenant_id 必须存在（来自 JWT 或 x-tenant-id）。
    - user_id 可选（匿名读场景允许缺失），写操作请使用 require_user。
    """
    payload = None
    if credentials:
        payload = decode_token(credentials.credentials)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token")

    tenant_id = (payload or {}).get("tenant_id") or x_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant_id")

    raw_roles = (payload or {}).get("roles") or []
    if isinstance(raw_roles, str):
        roles = [raw_roles]
    elif isinstance(raw_roles, list):
        roles = [str(r) for r in raw_roles if r is not None]
    else:
        roles = []

    user_id = None
    username = None
    if payload:
        user_id = payload.get("user_id") or payload.get("sub")
        username = payload.get("username")

    return Principal(
        tenant_id=str(tenant_id),
        user_id=str(user_id) if user_id else None,
        username=str(username) if username else None,
        roles=roles,
    )


def require_user(principal: Principal = Depends(get_principal)) -> Principal:
    if not principal.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return principal


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> str | None:
    """Extract user_id from JWT; return None if missing/invalid."""
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return str(user_id)
