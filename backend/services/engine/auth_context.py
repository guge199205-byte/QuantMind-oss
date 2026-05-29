from __future__ import annotations

from typing import Optional, Tuple

from fastapi import HTTPException, Request, status


def get_authenticated_identity(request: Request) -> tuple[str, str]:
    """从 request.state.user 提取身份信息。"""
    user = getattr(request.state, "user", None) or {}
    user_id = str(user.get("user_id") or "").strip()
    tenant_id = str(user.get("tenant_id") or "default").strip() or "default"
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authenticated user context",
        )
    return user_id, tenant_id


def assert_identity_not_spoofed(
    *,
    auth_user_id: str,
    auth_tenant_id: str,
    provided_user_id: str | None = None,
    provided_tenant_id: str | None = None,
) -> None:
    """若 query/body 传入身份且与认证身份不一致，则拒绝。"""
    if provided_user_id and str(provided_user_id) != str(auth_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user_id does not match authenticated identity",
        )
    if provided_tenant_id and str(provided_tenant_id) != str(auth_tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="tenant_id does not match authenticated identity",
        )
