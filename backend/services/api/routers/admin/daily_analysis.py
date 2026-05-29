"""Admin proxy for Daily Stock Analysis engine API."""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Request, Response

router = APIRouter()

ENGINE_BASE_URL = os.getenv("ENGINE_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
PROXY_TIMEOUT = 120.0


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    summary="Proxy Daily Analysis requests to engine service",
)
async def proxy_to_engine(path: str, request: Request) -> Response:
    """Forward all /admin/daily-analysis/* requests to engine service."""
    url = f"{ENGINE_BASE_URL}/api/v1/daily-analysis/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length", "transfer-encoding"}
    }

    body = await request.body()

    async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
        )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
    )
