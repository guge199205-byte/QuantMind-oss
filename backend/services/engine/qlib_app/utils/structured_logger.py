"""Qlib App 结构化日志辅助工具。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional


def _stringify(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, str):
        return value.replace("\n", "\\n")
    if isinstance(value, (dict, list, tuple, set)):
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            return str(value)
    return str(value)


class StructuredTaskLogger:
    """将普通 logger 封装为固定 key=value 风格输出。"""

    def __init__(self, base_logger: logging.Logger, component: str, context: dict[str, Any] | None = None):
        self._base_logger = base_logger
        self._component = component.strip()
        self._context = {k: v for k, v in (context or {}).items() if v is not None}

    def _build_message(self, event: str, message: str | None = None, **fields: Any) -> str:
        parts = [f"event={event}"]
        if message:
            parts.append(f"message={_stringify(message)}")

        merged = {**self._context, **fields}
        for key in sorted(merged):
            value = merged[key]
            if value is None:
                continue
            parts.append(f"{key}={_stringify(value)}")

        return f"[{self._component}] " + " ".join(parts)

    def debug(self, event: str, message: str | None = None, **fields: Any) -> None:
        self._base_logger.debug(self._build_message(event, message, **fields))

    def info(self, event: str, message: str | None = None, **fields: Any) -> None:
        self._base_logger.info(self._build_message(event, message, **fields))

    def warning(self, event: str, message: str | None = None, **fields: Any) -> None:
        self._base_logger.warning(self._build_message(event, message, **fields))

    def error(self, event: str, message: str | None = None, **fields: Any) -> None:
        self._base_logger.error(self._build_message(event, message, **fields))

    def exception(self, event: str, message: str | None = None, **fields: Any) -> None:
        self._base_logger.exception(self._build_message(event, message, **fields))
