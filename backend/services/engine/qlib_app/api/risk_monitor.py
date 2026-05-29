"""
实时风控监控API端点

提供风控监控的HTTP和WebSocket接口
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.services.engine.qlib_app.services.backtest_persistence import (
    BacktestPersistence,
)
from backend.services.engine.qlib_app.services.risk_monitor_service import (
    RiskControlConfig,
    get_active_monitor,
    get_all_active_monitors,
    stop_risk_monitoring,
)
from backend.services.engine.qlib_app.websocket.connection_manager import ws_manager
from backend.shared.auth import decode_jwt_token
from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

logger = logging.getLogger(__name__)
router = APIRouter()


# ============ Schemas ============


class RiskControlConfigRequest(BaseModel):
    """风控配置请求"""

    max_drawdown_threshold: float = Field(0.20, ge=0, le=1, description="最大回撤阈值")
    sharpe_threshold: float = Field(0.5, ge=0, le=10, description="夏普比率阈值")
    volatility_threshold: float = Field(0.30, ge=0, le=1, description="波动率阈值")
    var_threshold: float = Field(-0.05, ge=-1, le=0, description="VaR阈值")
    position_concentration_threshold: float = Field(0.30, ge=0, le=1, description="单股持仓比例阈值")
    enable_auto_stop: bool = Field(False, description="是否启用自动停止")


class StartMonitoringRequest(BaseModel):
    """启动监控请求"""

    backtest_id: str = Field(..., description="回测ID")
    config: RiskControlConfigRequest | None = Field(None, description="风控配置")
    update_interval: int = Field(5, ge=1, le=60, description="更新间隔（秒）")


class MonitorStatusResponse(BaseModel):
    """监控状态响应"""

    backtest_id: str
    is_monitoring: bool
    config: dict
    alerts_summary: dict


# ============ HTTP Endpoints ============


@router.post("/risk-monitor/start", response_model=dict)
async def start_monitoring(request: StartMonitoringRequest):
    """
    启动实时风控监控

    注意: 此接口仅启动监控框架，实际数据由回测服务推送
    """
    try:
        # 转换配置
        if request.config:
            RiskControlConfig(
                max_drawdown_threshold=request.config.max_drawdown_threshold,
                sharpe_threshold=request.config.sharpe_threshold,
                volatility_threshold=request.config.volatility_threshold,
                var_threshold=request.config.var_threshold,
                position_concentration_threshold=request.config.position_concentration_threshold,
                enable_auto_stop=request.config.enable_auto_stop,
            )

        # 注意：这里只是注册监控意图
        # 实际监控由回测服务调用 start_risk_monitoring 启动
        return {
            "status": "registered",
            "backtest_id": request.backtest_id,
            "message": "风控监控已注册，等待回测数据推送",
            "config": request.config.dict() if request.config else None,
        }

    except Exception as e:
        StructuredTaskLogger(logger, "risk-monitor-api", {"backtest_id": request.backtest_id}).exception(
            "start_failed", "启动监控失败", error=e
        )
        raise HTTPException(status_code=500, detail=f"启动监控失败: {str(e)}")


@router.post("/risk-monitor/stop/{backtest_id}")
async def stop_monitoring_endpoint(backtest_id: str):
    """
    停止实时风控监控
    """
    try:
        await stop_risk_monitoring(backtest_id)
        return {
            "status": "stopped",
            "backtest_id": backtest_id,
            "message": "风控监控已停止",
        }

    except Exception as e:
        StructuredTaskLogger(logger, "risk-monitor-api", {"backtest_id": backtest_id}).exception(
            "stop_failed", "停止监控失败", error=e
        )
        raise HTTPException(status_code=500, detail=f"停止监控失败: {str(e)}")


@router.get("/risk-monitor/status/{backtest_id}", response_model=MonitorStatusResponse)
async def get_monitor_status(backtest_id: str):
    """
    获取监控状态
    """
    monitor = get_active_monitor(backtest_id)

    if not monitor:
        raise HTTPException(status_code=404, detail="监控器不存在")

    return MonitorStatusResponse(
        backtest_id=backtest_id,
        is_monitoring=monitor.is_monitoring,
        config={
            "max_drawdown_threshold": monitor.config.max_drawdown_threshold,
            "sharpe_threshold": monitor.config.sharpe_threshold,
            "volatility_threshold": monitor.config.volatility_threshold,
            "var_threshold": monitor.config.var_threshold,
            "position_concentration_threshold": monitor.config.position_concentration_threshold,
            "enable_auto_stop": monitor.config.enable_auto_stop,
        },
        alerts_summary=monitor.get_alerts_summary(),
    )


@router.get("/risk-monitor/active", response_model=list)
async def get_active_monitors():
    """
    获取所有活跃监控器
    """
    monitors = get_all_active_monitors()
    return [
        {
            "backtest_id": backtest_id,
            "is_monitoring": monitor.is_monitoring,
            "alerts_count": len(monitor.alerts),
        }
        for backtest_id, monitor in monitors.items()
    ]


# ============ WebSocket Endpoint ============


@router.websocket("/ws/risk-monitor/{backtest_id}")
async def risk_monitor_websocket(
    websocket: WebSocket,
    backtest_id: str,
    user_id: str | None = Query(None, description="用户ID"),
    tenant_id: str | None = Query("default", description="租户ID"),
    token: str | None = Query(None, description="访问令牌"),
):
    """
    实时风控监控WebSocket

    连接: ws://localhost:8001/api/v1/ws/risk-monitor/{backtest_id}?user_id=xxx

    消息类型:
    1. risk_update - 风险指标更新
    2. alert - 风险告警
    3. auto_stop - 自动停止通知

    消息格式:
    {
        "type": "risk_update",
        "backtest_id": "xxx",
        "metrics": {
            "current_value": 1050000,
            "total_return": 0.05,
            "volatility": 0.15,
            "sharpe_ratio": 1.2,
            "max_drawdown": -0.08,
            "var_95": -0.03,
            "cvar_95": -0.045
        },
        "alerts": [
            {
                "alert_type": "warning",
                "indicator": "volatility",
                "current_value": 0.15,
                "threshold": 0.12,
                "message": "波动率超过阈值",
                "timestamp": "2026-01-16T12:00:00"
            }
        ],
        "timestamp": "2026-01-16T12:00:00"
    }
    """
    try:
        raw_auth_header = websocket.headers.get("authorization", "")
        header_token = raw_auth_header.split(" ", 1)[1].strip() if raw_auth_header.lower().startswith("bearer ") else ""
        candidate_token = (token or header_token or "").strip()
        if not candidate_token:
            await websocket.close(code=1008, reason="missing websocket auth token")
            return
        payload = decode_jwt_token(candidate_token)
        auth_user_id = str(payload.get("user_id") or payload.get("id") or payload.get("sub") or "").strip()
        auth_tenant_id = str(payload.get("tenant_id") or "default").strip() or "default"
        if not auth_user_id:
            await websocket.close(code=1008, reason="invalid websocket token")
            return
        if user_id and str(user_id).strip() != auth_user_id:
            await websocket.close(code=1008, reason="websocket identity mismatch")
            return
        if tenant_id and str(tenant_id).strip() and str(tenant_id).strip() != auth_tenant_id:
            await websocket.close(code=1008, reason="websocket tenant mismatch")
            return

        status = await BacktestPersistence().get_status(
            backtest_id=backtest_id,
            tenant_id=auth_tenant_id,
            user_id=auth_user_id,
        )
        if not status:
            await websocket.close(code=1008, reason="websocket access denied")
            return
    except Exception as exc:
        StructuredTaskLogger(logger, "risk-monitor-api", {"backtest_id": backtest_id}).warning(
            "ws_rejected", "拒绝风控 WebSocket 连接", error=exc
        )
        await websocket.close(code=1008, reason="websocket access denied")
        return

    await ws_manager.connect(websocket, backtest_id)

    try:
        # 发送欢迎消息
        await ws_manager.send_personal_message(
            {
                "type": "connected",
                "backtest_id": backtest_id,
                "message": "风控监控WebSocket连接已建立",
            },
            websocket,
        )

        # 如果监控器存在，发送当前状态
        monitor = get_active_monitor(backtest_id)
        if monitor:
            await ws_manager.send_personal_message(
                {
                    "type": "monitor_status",
                    "backtest_id": backtest_id,
                    "is_monitoring": monitor.is_monitoring,
                    "alerts_summary": monitor.get_alerts_summary(),
                },
                websocket,
            )

        # 保持连接
        while True:
            try:
                data = await websocket.receive_text()

                # 处理心跳
                if data == "ping":
                    await websocket.send_text("pong")
                elif data == "status":
                    # 返回当前状态
                    monitor = get_active_monitor(backtest_id)
                    if monitor:
                        await ws_manager.send_personal_message(
                            {
                                "type": "monitor_status",
                                "backtest_id": backtest_id,
                                "is_monitoring": monitor.is_monitoring,
                                "alerts_summary": monitor.get_alerts_summary(),
                            },
                            websocket,
                        )
                    else:
                        await ws_manager.send_personal_message(
                            {
                                "type": "error",
                                "message": "监控器不存在",
                            },
                            websocket,
                        )

            except WebSocketDisconnect:
                break
            except Exception as e:
                StructuredTaskLogger(logger, "risk-monitor-api", {"backtest_id": backtest_id}).exception(
                    "ws_message_failed", "WebSocket消息处理错误", error=e
                )
                break

    finally:
        await ws_manager.disconnect(websocket, backtest_id)
