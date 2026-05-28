"""
Data Gateway 反向代理
将 /api/v1/data/* 请求代理到 data-gateway 服务
"""

import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response, StreamingResponse

router = APIRouter(tags=["DataGateway"])

DATA_GATEWAY_URL = os.getenv("DATA_GATEWAY_URL", "http://quantmind-data-gateway:8004").rstrip("/")

_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


def _forward_headers(request: Request) -> dict[str, str]:
    return {k: v for k, v in request.headers.items() if k.lower() not in _HOP_HEADERS}


@router.api_route("/api/v1/data/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_data_gateway(path: str, request: Request):
    """代理 /api/v1/data/* 到 data-gateway 的 /api/v1/*"""
    upstream_url = f"{DATA_GATEWAY_URL}/api/v1/{path}"
    if request.url.query:
        upstream_url += f"?{request.url.query}"

    method = request.method.upper()
    headers = _forward_headers(request)
    body = await request.body()

    timeout = httpx.Timeout(connect=5.0, read=60.0, write=60.0, pool=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method, upstream_url,
                content=body if body else None,
                headers=headers,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers={"content-type": resp.headers.get("content-type", "application/json")},
            )
    except httpx.HTTPError:
        return PlainTextResponse("Data Gateway 服务不可达", status_code=502)
