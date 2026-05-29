"""Qlib API 身份与租户校验辅助函数。"""

from typing import Optional

from fastapi import Request

from backend.services.engine.auth_context import (
    assert_identity_not_spoofed,
    get_authenticated_identity,
)


def identity_from_request(
    request: Request,
    *,
    provided_user_id: str | None = None,
    provided_tenant_id: str | None = None,
) -> tuple[str, str]:
    auth_user_id, auth_tenant_id = get_authenticated_identity(request)
    assert_identity_not_spoofed(
        auth_user_id=auth_user_id,
        auth_tenant_id=auth_tenant_id,
        provided_user_id=provided_user_id,
        provided_tenant_id=provided_tenant_id,
    )
    return auth_user_id, auth_tenant_id
