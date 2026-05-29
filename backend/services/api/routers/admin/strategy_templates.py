"""
管理员策略模板代理路由
鉴权后将请求转发到 engine 服务的 /api/v1/admin/strategy-templates/*
"""

import logging
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.services.api.user_app.middleware.auth import require_admin
from backend.shared.auth import get_internal_call_secret

logger = logging.getLogger(__name__)

router = APIRouter()

_ENGINE_BASE_URL = os.getenv("ENGINE_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
_ENGINE_INTERNAL_SECRET = get_internal_call_secret()
_ENGINE_TEMPLATES_BASE = f"{_ENGINE_BASE_URL}/api/v1/admin/strategy-templates"

_INTERNAL_HEADERS = {
    "X-Internal-Call": _ENGINE_INTERNAL_SECRET,
}


async def _proxy(
    method: str,
    url: str,
    current_user: dict,
    json_body: Any | None = None,
) -> dict:
    headers = {
        **_INTERNAL_HEADERS,
        "X-User-Id": str(current_user.get("user_id", "admin")),
        "X-Tenant-Id": str(current_user.get("tenant_id", "default")),
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method, url, json=json_body, headers=headers)
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=resp.status_code,
                detail=resp.json().get("detail", resp.text[:500]),
            )
        return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("代理请求 engine 失败 [%s %s]: %s", method, url, e)
        raise HTTPException(status_code=502, detail=f"Engine 服务不可用: {e}")


# ---------------------------------------------------------------------------
# 端点（统一鉴权：require_admin）
# ---------------------------------------------------------------------------


@router.get("")
async def list_templates(
    current_user: dict = Depends(require_admin),
):
    """列出所有策略模板（管理员视图，含完整代码）。"""
    return await _proxy("GET", _ENGINE_TEMPLATES_BASE, current_user)


@router.post("", status_code=201)
async def create_template(
    request: Request,
    current_user: dict = Depends(require_admin),
):
    """新建策略模板。"""
    body = await request.json()
    return await _proxy("POST", _ENGINE_TEMPLATES_BASE, current_user, json_body=body)


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    request: Request,
    current_user: dict = Depends(require_admin),
):
    """更新策略模板。"""
    body = await request.json()
    url = f"{_ENGINE_TEMPLATES_BASE}/{template_id}"
    return await _proxy("PUT", url, current_user, json_body=body)


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    current_user: dict = Depends(require_admin),
):
    """删除策略模板。"""
    url = f"{_ENGINE_TEMPLATES_BASE}/{template_id}"
    return await _proxy("DELETE", url, current_user)
