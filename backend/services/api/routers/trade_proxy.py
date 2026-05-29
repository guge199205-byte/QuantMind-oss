"""
Trade 服务代理路由 (V2 健壮版)

将订单、持仓、模拟盘等请求透明转发到交易服务 (8002)。
"""

import asyncio
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Request, Response

from backend.services.api.routers.proxy_error_mapping import map_upstream_http_error
from backend.services.api.user_app.middleware.auth import get_optional_user

logger = logging.getLogger(__name__)

TRADE_BASE_URL = os.getenv("TRADE_SERVICE_URL", "http://trade-core:8002").rstrip("/")

router = APIRouter(tags=["Trade-Proxy"])

_SKIP_HEADERS = {"host", "content-length", "transfer-encoding"}


async def _do_proxy(request: Request, user: dict | None = None) -> Response:
    path = request.url.path

    # 兼容旧版前端：重写路径到 /api/v1
    if path.startswith("/internal/strategy") or \
       path.startswith("/simulation") or \
       path.startswith("/real-trading"):
        if not path.startswith("/api/v1"):
            path = f"/api/v1{path}"

    url = f"{TRADE_BASE_URL}{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = {k: v for k, v in request.headers.items() if k.lower() not in _SKIP_HEADERS}

    # 显式注入身份
    if user:
        headers["X-User-Id"] = str(user.get("user_id") or "")
        headers["X-Tenant-Id"] = str(user.get("tenant_id") or "default")
    else:
        user_from_state = getattr(request.state, "user", None)
        if user_from_state:
            headers["X-User-Id"] = str(user_from_state.get("user_id") or "")
            headers["X-Tenant-Id"] = str(user_from_state.get("tenant_id") or "default")

    body = await request.body()

    logger.debug(f"Proxying request: {request.method} {url}")

    max_retries = 3
    last_exc = None

    for attempt in range(max_retries):
        try:
            # 简化 client，不再强制本地地址或复杂的 transport 逻辑
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                resp = await client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    content=body if body else None,
                    follow_redirects=True,
                )

            resp_headers = {
                k: v
                for k, v in resp.headers.items()
                if k.lower() not in {"content-encoding", "content-length", "transfer-encoding"}
            }
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=resp_headers,
                media_type=resp.headers.get("content-type"),
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            last_exc = exc
            logger.warning(f"⚠️ Trade Proxy Attempt {attempt + 1} failed: {exc}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 1.5
                await asyncio.sleep(wait_time)
                continue
            break
        except Exception as exc:
            last_exc = exc
            break

    logger.error(f"❌ TRADE PROXY FINAL FAILURE: {request.method} {url} -> {type(last_exc).__name__}: {last_exc}")
    raise map_upstream_http_error("trade", last_exc or Exception("Unknown trade proxy error"))


@router.api_route("/api/v1/simulation", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
@router.api_route(
    "/api/v1/simulation/{p:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"], include_in_schema=False
)
@router.api_route("/api/v1/real-trading", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
@router.api_route(
    "/api/v1/real-trading/{p:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], include_in_schema=False
)
@router.api_route("/api/v1/orders", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
@router.api_route(
    "/api/v1/orders/{p:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], include_in_schema=False
)
@router.api_route("/api/v1/trades", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
@router.api_route("/api/v1/trades/{p:path}", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
@router.api_route("/api/v1/portfolios", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
@router.api_route(
    "/api/v1/portfolios/{p:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], include_in_schema=False
)
@router.api_route("/api/v1/internal/strategy", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
@router.api_route(
    "/api/v1/internal/strategy/{p:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    include_in_schema=False,
)
# 兼容旧版前端路径（不带 /api/v1 前缀）
@router.api_route("/internal/strategy", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
@router.api_route(
    "/internal/strategy/{p:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    include_in_schema=False,
)
@router.api_route("/simulation", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
@router.api_route(
    "/simulation/{p:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    include_in_schema=False,
)
@router.api_route("/real-trading", methods=["GET", "POST", "OPTIONS"], include_in_schema=False)
@router.api_route(
    "/real-trading/{p:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    include_in_schema=False,
)
async def trade_proxy_handler(request: Request, user: dict | None = Depends(get_optional_user)):
    return await _do_proxy(request, user)
