from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class Envelope(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Any | None = None
    trace_id: str | None = None


def success(data: Any = None, message: str = "ok") -> dict:
    return Envelope(code=0, message=message, data=data).model_dump()


def error(code: int, message: str, data: Any = None) -> dict:
    return Envelope(code=code, message=message, data=data).model_dump()
