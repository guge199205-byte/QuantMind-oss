from __future__ import annotations

from datetime import datetime
from typing import Dict, List


class MarketDataService:
    """最小市场数据服务封装。"""

    async def get_market_data(
        self,
        *,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        timeframe: str,
    ) -> dict:
        return {
            "symbols": symbols,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timeframe": timeframe,
            "bars": {},
        }
