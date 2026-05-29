"""
OpenAPI helpers.
"""

from __future__ import annotations

import re

from fastapi.routing import APIRoute


def quantmind_generate_unique_id(route: APIRoute) -> str:
    """Generate stable and unique OpenAPI operationId."""
    methods = "_".join(sorted(m.lower() for m in (route.methods or []) if m))
    path = re.sub(r"[^a-zA-Z0-9]+", "_", route.path_format).strip("_").lower()
    name = (route.name or "op").strip().lower()
    return f"{name}_{path}_{methods}"
