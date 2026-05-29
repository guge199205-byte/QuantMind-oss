"""Qlib 身份校验工具"""

from typing import Optional


def _identity_from_request(
    request,
    *,
    provided_user_id: str | None = None,
    provided_tenant_id: str | None = None,
):
    from backend.services.engine.auth_context import (
        assert_identity_not_spoofed,
        get_authenticated_identity,
    )

    auth_user_id, auth_tenant_id = get_authenticated_identity(request)
    assert_identity_not_spoofed(
        auth_user_id=auth_user_id,
        auth_tenant_id=auth_tenant_id,
        provided_user_id=provided_user_id,
        provided_tenant_id=provided_tenant_id,
    )
    return auth_user_id, auth_tenant_id
