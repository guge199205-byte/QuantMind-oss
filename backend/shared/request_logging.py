"""
Unified request access logging middleware.
"""

from __future__ import annotations

import logging
import time
from typing import Tuple

from fastapi import FastAPI, Request
from fastapi.responses import Response

try:
    from uvicorn.protocols.utils import ClientDisconnected as _UvicornClientDisconnected
except Exception:  # pragma: no cover - uvicorn version compatibility fallback
    _UvicornClientDisconnected = None  # type: ignore[assignment]

from backend.shared.auth import decode_jwt_token

logger = logging.getLogger(__name__)


def _is_client_disconnected_error(exc: Exception) -> bool:
    if _UvicornClientDisconnected is not None and isinstance(exc, _UvicornClientDisconnected):
        return True
    if isinstance(exc, (ConnectionResetError, BrokenPipeError)):
        return True
    return exc.__class__.__name__ in {"ClientDisconnected", "EndOfStream"}


def _looks_like_jwt(token: str) -> bool:
    parts = token.split(".")
    return len(parts) == 3 and all(part.strip() for part in parts)


class _UvicornAccessLogFilter(logging.Filter):
    def __init__(self, excluded_prefixes: tuple[str, ...]):
        super().__init__()
        self._excluded_prefixes = excluded_prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "uvicorn.access":
            return True

        args = getattr(record, "args", ())
        if isinstance(args, tuple) and len(args) >= 5:
            full_path = str(args[2] or "")
            if any(full_path.startswith(prefix) for prefix in self._excluded_prefixes):
                return False
        return True


def extract_identity_from_request(request: Request) -> tuple[str, str]:
    """
    Extract tenant_id and user_id from headers / JWT.

    Priority:
    1) X-Tenant-Id / X-User-Id headers
    2) Bearer token payload (tenant_id, sub/user_id)
    3) defaults: tenant_id=default, user_id=anonymous
    """
    tenant_id = (request.headers.get("X-Tenant-Id") or "").strip()
    user_id = (request.headers.get("X-User-Id") or "").strip()

    if tenant_id and user_id:
        return tenant_id, user_id

    if "/bridge/" in request.url.path:
        if not tenant_id:
            tenant_id = "default"
        if not user_id:
            user_id = "anonymous"
        return tenant_id, user_id

    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token and _looks_like_jwt(token):
            try:
                payload = decode_jwt_token(token)
                tenant_id = tenant_id or str(payload.get("tenant_id") or "").strip()
                user_id = user_id or str(payload.get("sub") or payload.get("user_id") or "").strip()
            except Exception:
                # Keep middleware non-blocking for logging purposes.
                pass

    if not tenant_id:
        tenant_id = "default"
    if not user_id:
        user_id = "anonymous"

    return tenant_id, user_id


def install_access_log_middleware(app: FastAPI, service_name: str) -> None:
    """Install standardized access-log middleware."""

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, _UvicornAccessLogFilter) for f in uvicorn_access_logger.filters):
        uvicorn_access_logger.addFilter(_UvicornAccessLogFilter(("/bridge/",)))

    @app.middleware("http")
    async def _access_log_middleware(request: Request, call_next):
        started = time.perf_counter()

        tenant_id, user_id = extract_identity_from_request(request)
        request.state.tenant_id = tenant_id
        request.state.user_id = user_id

        # Bridge 心跳和账户快照频率很高，属于内部同步流量，不进统一 access log。
        if "/bridge/" in request.url.path:
            try:
                return await call_next(request)
            except Exception as exc:
                if _is_client_disconnected_error(exc):
                    return Response(status_code=499)
                raise

        try:
            response = await call_next(request)
        except Exception as exc:
            if _is_client_disconnected_error(exc):
                return Response(status_code=499)
            raise

        duration_ms = (time.perf_counter() - started) * 1000.0
        request_id = getattr(getattr(request, "state", None), "request_id", "") or "-"
        logger.info(
            "access service=%s request_id=%s tenant_id=%s user_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            service_name,
            request_id,
            tenant_id,
            user_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
