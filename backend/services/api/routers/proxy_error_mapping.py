"""
Unified upstream proxy error mapping.
"""

from __future__ import annotations

import httpx
from fastapi import HTTPException


def map_upstream_http_error(service_name: str, exc: Exception) -> HTTPException:
    """
    Map upstream transport errors to consistent gateway responses.
    """
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        status_code = 503
        reason = "connect_error"
    elif isinstance(exc, httpx.ReadTimeout):
        status_code = 504
        reason = "read_timeout"
    elif isinstance(exc, httpx.TimeoutException):
        status_code = 504
        reason = "timeout"
    else:
        status_code = 502
        reason = "upstream_error"

    return HTTPException(
        status_code=status_code,
        detail={
            "message": f"{service_name} upstream unavailable",
            "service": service_name,
            "reason": reason,
            "error": str(exc),
        },
    )
