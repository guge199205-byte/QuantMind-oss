"""
Request ID middleware helper.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request


def install_request_id_middleware(app: FastAPI) -> None:
    """Attach request-id middleware to a FastAPI app."""

    @app.middleware("http")
    async def _request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
