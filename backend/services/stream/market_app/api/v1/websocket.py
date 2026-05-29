"""WebSocket endpoint for real-time data streaming"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

logger = logging.getLogger(__name__)


# 连接管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[WebSocket, set[str]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = set()
        logger.info(f"WebSocket connected: {id(websocket)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]
        logger.info(f"WebSocket disconnected: {id(websocket)}")

    def subscribe(self, websocket: WebSocket, symbols: list):
        if websocket in self.active_connections:
            self.active_connections[websocket].update(symbols)
            logger.info(f"Subscribed to {symbols}")

    def unsubscribe(self, websocket: WebSocket, symbols: list):
        if websocket in self.active_connections:
            self.active_connections[websocket].difference_update(symbols)
            logger.info(f"Unsubscribed from {symbols}")

    async def send_message(self, websocket: WebSocket, message: dict):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def broadcast_to_subscribers(self, symbol: str, data: dict):
        """向订阅了该股票的客户端广播数据"""
        for websocket, subscribed_symbols in self.active_connections.items():
            if symbol in subscribed_symbols:
                await self.send_message(websocket, data)


manager = ConnectionManager()


@router.websocket("/ws/market")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点 - 实时行情推送"""
    await manager.connect(websocket)

    # 从依赖注入获取数据库会话较复杂，这里简化处理
    # 实际生产环境应该使用适当的依赖注入

    try:
        # 发送欢迎消息
        await manager.send_message(
            websocket,
            {
                "type": "connected",
                "message": "Market data WebSocket connected",
                "timestamp": datetime.now().timestamp(),
            },
        )

        # 启动心跳任务
        heartbeat_task = asyncio.create_task(send_heartbeat(websocket))

        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)

            action = message.get("action")

            if action == "subscribe":
                # 订阅
                symbols = message.get("symbols", [])
                manager.subscribe(websocket, symbols)

                await manager.send_message(
                    websocket,
                    {
                        "type": "subscribed",
                        "symbols": symbols,
                        "timestamp": datetime.now().timestamp(),
                    },
                )

            elif action == "unsubscribe":
                # 取消订阅
                symbols = message.get("symbols", [])
                manager.unsubscribe(websocket, symbols)

                await manager.send_message(
                    websocket,
                    {
                        "type": "unsubscribed",
                        "symbols": symbols,
                        "timestamp": datetime.now().timestamp(),
                    },
                )

            elif action == "ping":
                # 心跳响应
                await manager.send_message(
                    websocket,
                    {"type": "pong", "timestamp": datetime.now().timestamp()},
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        heartbeat_task.cancel()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
        if not heartbeat_task.done():
            heartbeat_task.cancel()


async def send_heartbeat(websocket: WebSocket):
    """发送心跳"""
    try:
        while True:
            await asyncio.sleep(30)  # 每30秒发送一次心跳
            await manager.send_message(
                websocket,
                {"type": "heartbeat", "timestamp": datetime.now().timestamp()},
            )
    except asyncio.CancelledError:
        pass


"""
注意：企业级金融业务禁止内置任何模拟/演示行情推送逻辑。
WebSocket 推送应由真实数据源订阅/撮合结果驱动（例如从 Redis/DB/行情总线读取）。
"""
