"""Qlib 风险路由"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body

from backend.services.engine.qlib_app import get_qlib_service
from backend.services.engine.qlib_app.api.identity import _identity_from_request
from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

router = APIRouter(tags=["qlib"])

logger = logging.getLogger(__name__)


@router.get("/risk/{backtest_id}/metrics")
async def get_risk_metrics(
    request: Request,
    backtest_id: str,
    tenant_id: str | None = Query(None, description="租户ID（已废弃，自动使用认证身份）"),
    service: Any = Depends(get_qlib_service),
) -> dict[str, Any]:
    """获取风险指标"""
    try:
        from backend.services.engine.qlib_app.services.risk_monitor import RiskMonitor

        auth_user_id, auth_tenant_id = _identity_from_request(request, provided_tenant_id=tenant_id)
        result = await service.get_result(
            backtest_id,
            tenant_id=auth_tenant_id,
            user_id=auth_user_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="回测结果不存在")

        result_dict = result.dict() if hasattr(result, "dict") else result
        equity_curve = result_dict.get("equity_curve", [])

        monitor = RiskMonitor()
        metrics = monitor.calculate_risk_metrics(equity_curve)

        return {"backtest_id": backtest_id, "metrics": metrics}
    except HTTPException:
        raise
    except Exception as e:
        StructuredTaskLogger(
            logger,
            "risk-api",
            {"endpoint": "metrics", "backtest_id": backtest_id, "tenant_id": auth_tenant_id},
        ).exception("failed", "获取风险指标失败", error=e)
        raise HTTPException(status_code=500, detail=f"获取风险指标失败: {str(e)}")


@router.get("/risk/{backtest_id}/alerts")
async def get_risk_alerts(
    request: Request,
    backtest_id: str,
    tenant_id: str | None = Query(None, description="租户ID（已废弃，自动使用认证身份）"),
    service: Any = Depends(get_qlib_service),
) -> dict[str, Any]:
    """获取风险预警"""
    try:
        from backend.services.engine.qlib_app.services.risk_monitor import RiskMonitor

        auth_user_id, auth_tenant_id = _identity_from_request(request, provided_tenant_id=tenant_id)
        result = await service.get_result(
            backtest_id,
            tenant_id=auth_tenant_id,
            user_id=auth_user_id,
        )
        if not result:
            raise HTTPException(status_code=404, detail="回测结果不存在")

        result_dict = result.dict() if hasattr(result, "dict") else result
        equity_curve = result_dict.get("equity_curve", [])

        monitor = RiskMonitor()
        metrics = monitor.calculate_risk_metrics(equity_curve)
        alerts = monitor.check_alerts(metrics)
        daily_alerts = monitor.check_daily_alerts(equity_curve)

        all_alerts = alerts + daily_alerts

        return {
            "backtest_id": backtest_id,
            "alerts": all_alerts,
            "total_alerts": len(all_alerts),
        }
    except HTTPException:
        raise
    except Exception as e:
        StructuredTaskLogger(
            logger,
            "risk-api",
            {"endpoint": "alerts", "backtest_id": backtest_id, "tenant_id": auth_tenant_id},
        ).exception("failed", "获取风险预警失败", error=e)
        raise HTTPException(status_code=500, detail=f"获取风险预警失败: {str(e)}")


@router.post("/risk/{backtest_id}/config")
async def update_risk_config(
    request: Request,
    backtest_id: str,
    config: dict[str, Any] = Body(...),
    tenant_id: str | None = Query(None, description="租户ID（已废弃，自动使用认证身份）"),
    service: Any = Depends(get_qlib_service),
) -> dict[str, str]:
    """更新风险配置（暂存在内存中，未持久化）"""
    auth_user_id, auth_tenant_id = _identity_from_request(request, provided_tenant_id=tenant_id)
    status_obj = await service.get_status(
        backtest_id,
        tenant_id=auth_tenant_id,
        user_id=auth_user_id,
    )
    if status_obj.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="回测结果不存在")
    StructuredTaskLogger(
        logger,
        "risk-api",
        {"endpoint": "config", "backtest_id": backtest_id, "tenant_id": auth_tenant_id},
    ).info("update_config", "更新回测风险配置", config=config)
    return {"message": "风险配置已更新", "backtest_id": backtest_id}
