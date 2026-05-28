"""
Dashboard (Streamlit) 反向代理

将 Streamlit 容器的 Web 界面通过 /api/v1/dashboard/ 路径暴露给前端 iframe 嵌入。

参考 qwenpaw_ui_proxy.py 的实现模式。
"""

import os

import httpx
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse, Response, StreamingResponse

router = APIRouter(tags=["Dashboard"])

DASHBOARD_BASE_URL = os.getenv("DASHBOARD_BASE_URL", "http://quantmind-dashboard:8501").rstrip("/")
DASHBOARD_WS_URL = DASHBOARD_BASE_URL.replace("http://", "ws://").replace("https://", "wss://")

_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}

_STATIC_MIME = {
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".map": "application/json",
}

# 注入到 HTML <head> 的拦截脚本：
# 重写 fetch/XHR 的 /api/ 路径 -> /api/v1/dashboard-api/
# 重写 WebSocket URL -> /api/v1/dashboard-ws/
_API_REWRITE_SCRIPT = r"""<script>
(function(){
  var API_P='/api/v1/dashboard-api/';
  var WS_P='/api/v1/dashboard-ws/';
  var UI_P='/api/v1/dashboard/';

  function rwApi(u){
    if(typeof u!=='string') return u;
    if(u.charAt(0)==='/' && u.startsWith('/_stcore/')) return API_P+'_stcore/'+u.slice(9);
    if(u.charAt(0)==='/' && u.startsWith('/api/')) return API_P+u.slice(5);
    return u;
  }
  function rwWs(u){
    if(typeof u!=='string') return u;
    var ws=(window.location.protocol==='https:'?'wss:':'ws:')+'//'+window.location.host;
    // Absolute ws://... URL
    if(u.startsWith('ws://') || u.startsWith('wss://')){
      try{
        var x=new URL(u);
        var p=x.pathname;
        // Strip the UI prefix (e.g. /api/v1/dashboard/) if present
        if(p.indexOf(UI_P)===0) p=p.slice(UI_P.length-1);
        else if(p.charAt(0)==='/') p=p.slice(1);
        return ws+WS_P+p;
      }catch(e){ return u; }
    }
    // Relative path like /_stcore/stream
    if(u.charAt(0)==='/'){
      var p2=u;
      if(p2.indexOf(UI_P)===0) p2=p2.slice(UI_P.length-1);
      else p2=p2.slice(1);
      return ws+WS_P+p2;
    }
    return u;
  }
  function rwAsset(u){
    if(typeof u!=='string') return u;
    if(u.charAt(0)==='/' && u.startsWith('/assets/')) return UI_P+'assets/'+u.slice(8);
    if(u.charAt(0)==='/' && u.startsWith('/static/')) return UI_P+'static/'+u.slice(8);
    if(u.charAt(0)==='/' && u.startsWith('/favicon.ico')) return UI_P+'favicon.ico';
    if(u.charAt(0)==='/' && u.startsWith('/_stcore/')) return UI_P+'_stcore/'+u.slice(9);
    return u;
  }
  function rwAll(u){ return rwAsset(rwApi(rwWs(u))); }

  // Intercept fetch
  var _f=window.fetch;
  window.fetch=function(u,o){
    var url=(typeof u==='string')?u:(u instanceof URL)?u.toString():u;
    url=rwAll(url);
    return _f.call(this,url,o);
  };

  // Intercept XMLHttpRequest
  var _o=XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open=function(m,u){
    return _o.apply(this,[m,rwAll(u)]);
  };

  // Intercept WebSocket
  var _ws=WebSocket;
  window.WebSocket=function(url,protocols){
    return new _ws(rwWs(url),protocols);
  };
  window.WebSocket.prototype=_ws.prototype;
  window.WebSocket.CONNECTING=_ws.CONNECTING;
  window.WebSocket.OPEN=_ws.OPEN;
  window.WebSocket.CLOSING=_ws.CLOSING;
  window.WebSocket.CLOSED=_ws.CLOSED;
})();
</script>"""


def _guess_mime(path: str) -> str:
    from pathlib import PurePosixPath
    suffix = PurePosixPath(path).suffix.lower()
    return _STATIC_MIME.get(suffix, "application/octet-stream")


def _forward_headers(request: Request) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in request.headers.items():
        if key.lower() in _HOP_HEADERS:
            continue
        out[key] = value
    return out


async def _proxy_static(path: str, accept: str) -> Response:
    """代理静态资源（GET only）。"""
    url = f"{DASHBOARD_BASE_URL}/{path.lstrip('/')}"
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"Accept": accept})
    except httpx.HTTPError:
        return PlainTextResponse("Dashboard 服务不可达", status_code=502)

    content_type = resp.headers.get("content-type", "")
    body = resp.content

    # HTML: 重写资源路径 + 注入 API 拦截脚本
    if "text/html" in content_type and body:
        html = body.decode("utf-8", errors="replace")
        # 静态资源路径重写
        html = html.replace('src="/assets/', 'src="/api/v1/dashboard/assets/')
        html = html.replace('href="/assets/', 'href="/api/v1/dashboard/assets/')
        html = html.replace('src="/static/', 'src="/api/v1/dashboard/static/')
        html = html.replace('href="/static/', 'href="/api/v1/dashboard/static/')
        html = html.replace('href="/favicon.ico"', 'href="/api/v1/dashboard/favicon.ico"')
        html = html.replace('src="/favicon.ico"', 'src="/api/v1/dashboard/favicon.ico"')
        # 在 <head> 后注入 API 路径拦截脚本
        html = html.replace("<head>", "<head>" + _API_REWRITE_SCRIPT, 1)
        return HTMLResponse(content=html, status_code=resp.status_code)

    resp_headers = {}
    if "content-type" not in resp.headers:
        guessed = _guess_mime(path)
        resp_headers["content-type"] = guessed
    else:
        resp_headers["content-type"] = content_type

    if any(
        path.endswith(ext)
        for ext in (".js", ".mjs", ".css", ".woff2", ".woff", ".ttf", ".svg", ".png", ".webp")
    ):
        resp_headers["cache-control"] = "public, max-age=3600"

    return Response(content=body, status_code=resp.status_code, headers=resp_headers)


# ---------- Dashboard 静态资源路由 ----------


@router.get("/api/v1/dashboard/{path:path}")
async def proxy_dashboard_ui(path: str, request: Request):
    """代理 Dashboard 的所有静态资源。"""
    accept = request.headers.get("accept", "*/*")
    return await _proxy_static(path, accept)


@router.get("/api/v1/dashboard")
async def proxy_dashboard_ui_index(request: Request):
    """代理 Dashboard 首页。"""
    accept = request.headers.get("accept", "text/html,*/*")
    return await _proxy_static("", accept)


# ---------- Dashboard API 代理路由 ----------

_DASHBOARD_API_PREFIX = "/api/v1/dashboard-api/"
_UPSTREAM_API_PREFIX = "/"


async def _proxy_api(request: Request) -> Response:
    """通用 API 代理：将 /api/v1/dashboard-api/* 转发到 Dashboard /*。"""
    path = request.url.path.removeprefix(_DASHBOARD_API_PREFIX)
    upstream_url = f"{DASHBOARD_BASE_URL}{_UPSTREAM_API_PREFIX}{path}"

    if request.url.query:
        upstream_url += f"?{request.url.query}"

    method = request.method.upper()
    fwd_headers = _forward_headers(request)
    body = await request.body()

    timeout = httpx.Timeout(connect=5.0, read=120.0, write=120.0, pool=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "POST" and "text/event-stream" in fwd_headers.get("accept", ""):
                # Streaming SSE (Streamlit uses this for real-time updates)
                req = client.build_request(method, upstream_url, content=body, headers=fwd_headers)
                resp = await client.send(req, stream=True)

                if resp.status_code >= 400:
                    err_body = await resp.aread()
                    await resp.aclose()
                    await client.aclose()
                    return Response(
                        content=err_body,
                        status_code=resp.status_code,
                        media_type=resp.headers.get("content-type", "application/json"),
                    )

                async def _cleanup():
                    await resp.aclose()
                    await client.aclose()

                return StreamingResponse(
                    resp.aiter_raw(),
                    status_code=resp.status_code,
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                    background=_cleanup,
                )
            else:
                req = client.build_request(
                    method,
                    upstream_url,
                    content=body if body else None,
                    headers=fwd_headers,
                )
                resp = await client.send(req)

                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    headers={"content-type": resp.headers.get("content-type", "application/json")},
                )
    except httpx.HTTPError:
        return PlainTextResponse("Dashboard 服务不可达", status_code=502)


@router.api_route(
    f"{_DASHBOARD_API_PREFIX}{{path:path}}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def proxy_dashboard_api(path: str, request: Request):
    """代理 Dashboard API 调用（/api/v1/dashboard-api/* -> Dashboard /*）。"""
    return await _proxy_api(request)


# ---------- Dashboard WebSocket 代理路由 ----------


@router.websocket("/api/v1/dashboard-ws/{path:path}")
async def proxy_dashboard_ws(websocket: WebSocket, path: str):
    """代理 Dashboard WebSocket 连接。"""
    await websocket.accept()

    import asyncio

    upstream_url = f"{DASHBOARD_WS_URL}/{path}"
    if websocket.url.query:
        upstream_url += f"?{websocket.url.query}"

    try:
        import websockets
    except ImportError:
        try:
            await websocket.close(code=1011, reason="WebSocket proxy not available (websockets not installed)")
        except Exception:
            pass
        return

    try:
        async with websockets.connect(upstream_url) as upstream:

            async def client_to_upstream():
                try:
                    while True:
                        data = await websocket.receive_text()
                        await upstream.send(data)
                except WebSocketDisconnect:
                    pass
                except Exception:
                    pass

            async def upstream_to_client():
                try:
                    async for message in upstream:
                        await websocket.send_text(message)
                except Exception:
                    pass

            await asyncio.gather(
                client_to_upstream(),
                upstream_to_client(),
            )
    except Exception:
        try:
            await websocket.close(code=1011, reason="Upstream connection failed")
        except Exception:
            pass
