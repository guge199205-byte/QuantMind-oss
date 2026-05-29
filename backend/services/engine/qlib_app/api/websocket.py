"""WebSocket API 路由"""

import logging
import os
from typing import Optional, Tuple

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.services.engine.qlib_app.services.backtest_persistence import (
    BacktestPersistence,
)
from backend.services.engine.qlib_app.websocket.connection_manager import ws_manager
from backend.shared.auth import decode_jwt_token
from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

logger = logging.getLogger(__name__)
task_logger = StructuredTaskLogger(logger, "WebSocketAPI")
router = APIRouter()


def _resolve_identity_from_token(token: str) -> tuple[str, str]:
    payload = decode_jwt_token(token)
    user_id = str(payload.get("user_id") or payload.get("id") or payload.get("sub") or "").strip()
    tenant_id = str(payload.get("tenant_id") or "default").strip() or "default"
    if not user_id:
        raise ValueError("invalid token payload: missing user_id")
    return user_id, tenant_id


async def _assert_ws_access(backtest_id: str, user_id: str, tenant_id: str) -> None:
    status = await BacktestPersistence().get_status(
        backtest_id=backtest_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    if not status:
        raise PermissionError("backtest not found or access denied")


@router.websocket("/ws/backtest/{backtest_id}")
async def backtest_progress_websocket(
    websocket: WebSocket,
    backtest_id: str,
    user_id: str | None = Query(None, description="用户ID"),
    tenant_id: str | None = Query("default", description="租户ID"),
    token: str | None = Query(None, description="访问令牌"),
):
    """
    WebSocket端点 - 实时回测进度推送

    连接: ws://localhost:8001/api/v1/ws/backtest/{backtest_id}?user_id=xxx

    消息格式:
    {
        "type": "progress",  // progress | result | error
        "backtest_id": "xxx",
        "progress": 0.5,  // 0.0 ~ 1.0
        "status": "running",  // pending | running | completed | failed
        "message": "正在计算...",
        "timestamp": "2026-01-14T12:00:00"
    }
    """
    try:
        auth_user_id: str | None = None
        auth_tenant_id: str | None = None
        raw_auth_header = websocket.headers.get("authorization", "")
        header_token = raw_auth_header.split(" ", 1)[1].strip() if raw_auth_header.lower().startswith("bearer ") else ""
        candidate_token = (token or header_token or "").strip()

        if candidate_token:
            auth_user_id, auth_tenant_id = _resolve_identity_from_token(candidate_token)
        else:
            allow_query_identity = os.getenv("QLIB_WS_ALLOW_QUERY_IDENTITY", "false").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            if not allow_query_identity:
                await websocket.close(code=1008, reason="missing websocket auth token")
                return
            auth_user_id = str(user_id or "").strip()
            auth_tenant_id = str(tenant_id or "default").strip() or "default"
            if not auth_user_id:
                await websocket.close(code=1008, reason="missing websocket user identity")
                return

        if user_id and str(user_id).strip() != auth_user_id:
            await websocket.close(code=1008, reason="websocket identity mismatch")
            return
        if tenant_id and str(tenant_id).strip() and str(tenant_id).strip() != auth_tenant_id:
            await websocket.close(code=1008, reason="websocket tenant mismatch")
            return

        await _assert_ws_access(
            backtest_id=backtest_id,
            user_id=auth_user_id,
            tenant_id=auth_tenant_id,
        )
    except Exception as exc:
        task_logger.warning("ws_rejected", "拒绝 WebSocket 连接", backtest_id=backtest_id, error=str(exc))
        await websocket.close(code=1008, reason="websocket access denied")
        return

    await ws_manager.connect(websocket, backtest_id)

    try:
        # 发送欢迎消息
        await ws_manager.send_personal_message(
            {
                "type": "connected",
                "backtest_id": backtest_id,
                "message": "WebSocket连接已建立",
            },
            websocket,
        )

        # 保持连接，处理心跳
        while True:
            try:
                # 等待客户端消息（心跳）
                data = await websocket.receive_text()

                # 处理心跳
                if data == "ping":
                    await websocket.send_text("pong")
                elif data == "status":
                    # 返回当前状态
                    await ws_manager.send_personal_message(
                        {
                            "type": "status",
                            "backtest_id": backtest_id,
                            "connections": ws_manager.get_connection_count(backtest_id),
                        },
                        websocket,
                    )

            except WebSocketDisconnect:
                break
            except Exception as e:
                task_logger.error("ws_message_error", "WebSocket消息处理错误", error=str(e))
                break

    finally:
        await ws_manager.disconnect(websocket, backtest_id)


@router.get("/ws/stats")
async def get_websocket_stats():
    """获取WebSocket统计信息"""
    return {
        "total_connections": ws_manager.get_connection_count(),
        "active_rooms": ws_manager.get_active_rooms(),
    }
