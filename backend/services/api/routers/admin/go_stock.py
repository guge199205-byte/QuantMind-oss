"""Admin proxy for go-stock API service."""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Request, Response

router = APIRouter()

GO_STOCK_SERVICE_URL = os.getenv(
    "GO_STOCK_SERVICE_URL", "http://quantmind-go-stock:18080"
).rstrip("/")

PROXY_TIMEOUT = 60.0


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    summary="Proxy requests to go-stock API service",
)
async def proxy_to_go_stock(path: str, request: Request) -> Response:
    """Forward all /admin/go-stock/* requests to go-stock service."""
    url = f"{GO_STOCK_SERVICE_URL}/api/v1/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = {
        k: v
        for k, v in request.headers.items()
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
