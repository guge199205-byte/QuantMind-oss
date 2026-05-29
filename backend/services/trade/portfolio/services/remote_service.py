import logging

import httpx
from fastapi import HTTPException

from backend.services.trade.portfolio.config import settings

logger = logging.getLogger(__name__)


class RemoteService:
    """远程服务客户端 (Strategy Service & Real Trading Service)"""

    def __init__(self):
        self.strategy_base_url = settings.STRATEGY_SERVICE_URL
        self.trading_base_url = settings.REAL_TRADING_SERVICE_URL
        # 设置超时
        self.timeout = httpx.Timeout(10.0, connect=5.0)

    async def get_strategy_code(self, strategy_id: int, user_id: int, token: str) -> dict:
        """
        从 Strategy Service 获取策略详情 (包含代码/配置)
        """
        url = f"{self.strategy_base_url}/api/v1/strategies/{strategy_id}"
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                # 假设返回结构: {"code": 0, "msg": "success", "data": {...}}
                return data.get("data", {})
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to get strategy {strategy_id}: {e.response.text}")
                if e.response.status_code == 404:
                    raise HTTPException(status_code=404, detail="Strategy not found")
                raise HTTPException(status_code=500, detail="Failed to fetch strategy")
            except Exception as e:
                logger.error(f"Error connecting to Strategy Service: {e}")
                raise HTTPException(status_code=503, detail="Strategy Service unavailable")

    async def start_real_trading(
        self, user_id: str, strategy_code: str, strategy_filename: str = "strategy.py"
    ) -> dict:
        """
        调用 Real Trading Service 启动实盘
        """
        url = f"{self.trading_base_url}/api/v1/real-trading/start"

        # 构造 multipart/form-data
        files = {"file": (strategy_filename, strategy_code, "text/x-python")}
        data = {"user_id": user_id}

        async with httpx.AsyncClient(timeout=120.0) as client:  # 启动K8s可能较慢，增加超时
            try:
                response = await client.post(url, data=data, files=files)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to start real trading: {e.response.text}")
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"Real Trading Error: {e.response.text}",
                )
            except Exception as e:
                logger.error(f"Error connecting to Real Trading Service: {e}")
                raise HTTPException(status_code=503, detail="Real Trading Service unavailable")

    async def stop_real_trading(self, user_id: str) -> dict:
        """
        调用 Real Trading Service 停止实盘
        """
        url = f"{self.trading_base_url}/api/v1/real-trading/stop"
        data = {"user_id": user_id}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, data=data)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to stop real trading: {e.response.text}")
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"Real Trading Error: {e.response.text}",
                )
            except Exception as e:
                logger.error(f"Error connecting to Real Trading Service: {e}")
                raise HTTPException(status_code=503, detail="Real Trading Service unavailable")

    async def get_real_trading_status(self, user_id: str) -> dict:
        """
        获取实盘状态
        """
        url = f"{self.trading_base_url}/api/v1/real-trading/status"
        params = {"user_id": user_id}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, params=params)
                if response.status_code == 404:
                    return {"status": "not_running"}
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error connecting to Real Trading Service: {e}")
                # 不抛出异常，返回 unknown 状态以免阻塞查询
                return {"status": "unknown", "error": str(e)}


remote_service = RemoteService()
