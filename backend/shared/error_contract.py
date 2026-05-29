"""
Unified HTTP error response contract.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

try:
    from uvicorn.protocols.utils import ClientDisconnected  # type: ignore
except Exception:  # pragma: no cover - optional import path differences
    ClientDisconnected = None  # type: ignore

logger = logging.getLogger(__name__)


def _request_id_from_state(request: Request) -> str:
    return getattr(getattr(request, "state", None), "request_id", "") or ""


def _normalize_message(detail: Any, fallback: str) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail
    if isinstance(detail, dict):
        msg = detail.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg
    return fallback


def _is_client_disconnected(exc: BaseException) -> bool:
    if ClientDisconnected is not None and isinstance(exc, ClientDisconnected):
        return True

    if exc.__class__.__name__ == "ClientDisconnected" and exc.__class__.__module__.startswith("uvicorn"):
        return True

    nested = getattr(exc, "exceptions", None)
    if nested:
        try:
            return any(_is_client_disconnected(inner) for inner in nested if isinstance(inner, BaseException))
        except Exception:
            pass

    cause = getattr(exc, "__cause__", None)
    if isinstance(cause, BaseException) and _is_client_disconnected(cause):
        return True

    context = getattr(exc, "__context__", None)
    if isinstance(context, BaseException) and _is_client_disconnected(context):
        return True

    return False


def _build_error_payload(
    *,
    request: Request,
    code: str,
    message: str,
    detail: Any = None,
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": _request_id_from_state(request),
        }
    }
    if detail is not None:
        payload["detail"] = detail
    if errors:
        payload["errors"] = errors
    return payload


def install_error_contract_handlers(app: FastAPI) -> None:
    """Install unified exception handlers for HTTP APIs."""

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
        status_code = int(getattr(exc, "status_code", 500))
        detail = getattr(exc, "detail", None)
        message = _normalize_message(detail, fallback="Request failed")
        return JSONResponse(
            status_code=status_code,
            content=_build_error_payload(
                request=request,
                code=f"HTTP_{status_code}",
                message=message,
                detail=detail,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_build_error_payload(
                request=request,
                code="VALIDATION_ERROR",
                message="Request validation failed",
                detail="Request validation failed",
                errors=exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        if _is_client_disconnected(exc):
            logger.debug("Client disconnected path=%s request_id=%s", request.url.path, _request_id_from_state(request))
            return JSONResponse(
                status_code=499,
                content=_build_error_payload(
                    request=request,
                    code="CLIENT_DISCONNECTED",
                    message="Client disconnected",
                    detail="Client disconnected",
                ),
            )
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content=_build_error_payload(
                request=request,
                code="INTERNAL_ERROR",
                message="Internal server error",
                detail="Internal server error",
            ),
        )
