"""WebSocket 进度推送管理器

功能:
1. 管理WebSocket连接
2. 实时推送回测进度
3. 支持房间机制（按backtest_id分组）
4. 自动清理失效连接
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect
from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

logger = logging.getLogger(__name__)
task_logger = StructuredTaskLogger(logger, "WebSocketManager")


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        # backtest_id -> Set[WebSocket]
        self.active_connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, backtest_id: str):
        """接受新连接"""
        await websocket.accept()
        async with self._lock:
            if backtest_id not in self.active_connections:
                self.active_connections[backtest_id] = set()
            self.active_connections[backtest_id].add(websocket)
        task_logger.info(
            "ws_connected",
            "WebSocket连接已建立",
            backtest_id=backtest_id,
            connections=len(self.active_connections[backtest_id]),
        )

    async def disconnect(self, websocket: WebSocket, backtest_id: str):
        """断开连接"""
        async with self._lock:
            if backtest_id in self.active_connections:
                self.active_connections[backtest_id].discard(websocket)
                if not self.active_connections[backtest_id]:
                    # 房间为空，删除
                    del self.active_connections[backtest_id]
                task_logger.info("ws_disconnected", "WebSocket连接已断开", backtest_id=backtest_id)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """发送私有消息"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            task_logger.error("ws_send_failed", "发送消息失败", error=str(e))

    async def broadcast_to_room(self, message: dict, backtest_id: str):
        """向房间广播消息"""
        async with self._lock:
            connections = self.active_connections.get(backtest_id, set()).copy()

        if not connections:
            task_logger.debug("ws_room_empty", "房间无活跃连接", backtest_id=backtest_id)
            return

            # 记录失效连接
        dead_connections = []

        for websocket in connections:
            try:
                await websocket.send_json(message)
            except WebSocketDisconnect:
                dead_connections.append(websocket)
            except Exception as e:
                task_logger.error("ws_broadcast_failed", "广播消息失败", error=str(e))
                dead_connections.append(websocket)

                # 清理失效连接
        if dead_connections:
            async with self._lock:
                if backtest_id in self.active_connections:
                    for ws in dead_connections:
                        self.active_connections[backtest_id].discard(ws)
                    if not self.active_connections[backtest_id]:
                        del self.active_connections[backtest_id]
            task_logger.info("ws_dead_connections_cleaned", "清理了失效连接", backtest_id=backtest_id, count=len(dead_connections))

    async def broadcast_log(self, room_id: str, message: str):
        """广播日志消息"""
        if room_id in self.active_connections:
            # 构造符合前端期望的日志格式
            log_entry = {
                "type": "log",
                "message": message,
                "timestamp": datetime.now().isoformat(),
            }
            # 移除无效连接
            to_remove = []
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_json(log_entry)
                except Exception:
                    to_remove.append(connection)

            for conn in to_remove:
                await self.disconnect(conn, room_id)

    async def send_progress(self, backtest_id: str, progress: float, status: str, message: str = ""):
        """发送进度更新"""
        data = {
            "type": "progress",
            "backtest_id": backtest_id,
            "progress": progress,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        await self.broadcast_to_room(data, backtest_id)

    async def send_result(self, backtest_id: str, result: dict):
        """发送最终结果"""
        data = {
            "type": "result",
            "backtest_id": backtest_id,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
        await self.broadcast_to_room(data, backtest_id)

    async def send_error(
        self,
        backtest_id: str,
        error_code: str,
        error_message: str,
        details: dict = None,
    ):
        """发送错误信息"""
        data = {
            "type": "error",
            "backtest_id": backtest_id,
            "error_code": error_code,
            "error_message": error_message,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        }
        await self.broadcast_to_room(data, backtest_id)

    def get_connection_count(self, backtest_id: str = None) -> int:
        """获取连接数"""
        if backtest_id:
            return len(self.active_connections.get(backtest_id, set()))
        return sum(len(conns) for conns in self.active_connections.values())

    def get_active_rooms(self) -> list:
        """获取活跃房间列表"""
        return [
            {"backtest_id": room_id, "connections": len(conns)} for room_id, conns in self.active_connections.items()
        ]

        # 全局实例


ws_manager = ConnectionManager()
