"""Admin proxy for Daily Stock Analysis API service."""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Request, Response

router = APIRouter()

DSA_SERVICE_URL = os.getenv(
    "DSA_SERVICE_URL", "http://quantmind-dsa:8005"
).rstrip("/")

PROXY_TIMEOUT = 60.0


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    summary="Proxy requests to DSA API service",
)
async def proxy_to_dsa(path: str, request: Request) -> Response:
    """Forward all /admin/dsa/* requests to DSA service."""
    url = f"{DSA_SERVICE_URL}/{path}"
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
