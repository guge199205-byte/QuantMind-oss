import os
from typing import Any, Dict, Optional

import httpx


class StockSelectionClient:
    """调用 OpenClaw 的选股服务"""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url or os.getenv("OPENCLAW_BASE_URL", "http://127.0.0.1:8015")
        self.timeout = timeout

    async def select_stocks(
        self,
        query: str,
        limit: int = 200,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "query": query,
            "user_id": user_id,
            "limit": limit,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/openclaw/stock-selection",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
