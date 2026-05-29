"""Qlib 回测历史与结果路由"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from backend.services.engine.qlib_app import get_qlib_service
from backend.services.engine.qlib_app.api.history_filters import (
    _filter_legacy_optimization_clusters,
    _filter_optimization_sub_backtests,
)
from backend.services.engine.qlib_app.api.identity import _identity_from_request
from backend.services.engine.qlib_app.api.strategy_name import (
    _normalize_strategy_key,
    _resolve_strategy_display_name,
)
from backend.services.engine.qlib_app.schemas.backtest import QlibBacktestResult
router = APIRouter(tags=["qlib"])

logger = logging.getLogger(__name__)


@router.get("/results/{backtest_id}", response_model=QlibBacktestResult)
async def get_backtest_result(
    request: Request,
    backtest_id: str,
    tenant_id: str | None = Query(None, description="租户ID（已废弃，自动使用认证身份）"),
    exclude_trades: bool = Query(False, description="是否排除交易流水数据以加速返回"),
    service: Any = Depends(get_qlib_service),
) -> QlibBacktestResult:
    """获取回测结果"""
    auth_user_id, auth_tenant_id = _identity_from_request(request, provided_tenant_id=tenant_id)
    result = await service.get_result(
        backtest_id,
        tenant_id=auth_tenant_id,
        user_id=auth_user_id,
        exclude_trades=exclude_trades,
    )
    if not result:
        raise HTTPException(status_code=404, detail="回测结果不存在")

    if hasattr(result, "model_dump"):
        content = result.model_dump(mode="json")
    else:
        from fastapi.encoders import jsonable_encoder

        content = jsonable_encoder(result)

    if exclude_trades:
        content.pop("trades", None)
        content.pop("trade_list", None)
        content.pop("positions", None)

    return JSONResponse(content=content)


@router.get("/results/{backtest_id}/trades")
async def get_backtest_trades(
    request: Request,
    backtest_id: str,
    tenant_id: str | None = Query(None, description="租户ID（已废弃，自动使用认证身份）"),
    service: Any = Depends(get_qlib_service),
) -> dict[str, Any]:
    """独立获取回测成交流水，用于前端按需懒加载以提高响应速度"""
    auth_user_id, auth_tenant_id = _identity_from_request(request, provided_tenant_id=tenant_id)
    result = await service.get_result(
        backtest_id,
        tenant_id=auth_tenant_id,
        user_id=auth_user_id,
        exclude_trades=False,
    )
    if not result:
        raise HTTPException(status_code=404, detail="回测结果不存在")

    if hasattr(result, "model_dump"):
        content = result.model_dump(mode="json")
    else:
        from fastapi.encoders import jsonable_encoder

        content = jsonable_encoder(result)

    return JSONResponse(
        content={
            "trades": content.get("trades") or content.get("trade_list") or [],
            "positions": content.get("positions") or [],
        }
    )


@router.get("/history/{user_id}")
async def get_backtest_history(
    request: Request,
    user_id: str,
    tenant_id: str | None = Query(None, description="租户ID（已废弃，自动使用认证身份）"),
    include_optimization: bool = Query(False, description="是否包含参数优化产生的子回测记录"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="排序方向"),
    status: str | None = Query(None, description="状态过滤"),
    symbol: str | None = Query(None, description="股票代码过滤"),
    service: Any = Depends(get_qlib_service),
):
    """获取回测历史 (支持分页和排序)"""
    auth_user_id, auth_tenant_id = _identity_from_request(
        request,
        provided_user_id=user_id,
        provided_tenant_id=tenant_id,
    )
    results = await service.list_history(auth_user_id, auth_tenant_id, limit=max(page * page_size * 5, 200))

    def _field(item: Any, key: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            val = item.get(key)
        else:
            val = getattr(item, key, None)
        return val if val is not None else default

    def _history_source(item: Any) -> str:
        config = _field(item, "config", {}) or {}
        if isinstance(config, dict):
            source = str(config.get("history_source") or "manual").strip().lower()
            return source or "manual"
        return "manual"

    if not include_optimization:
        results = [r for r in results if _history_source(r) != "optimization"]
        results = await _filter_optimization_sub_backtests(results, user_id=auth_user_id, tenant_id=auth_tenant_id)
        results = _filter_legacy_optimization_clusters(results)

    if status:
        results = [r for r in results if _field(r, "status") == status]

    if symbol:
        results = [r for r in results if _field(r, "symbol") == symbol]

    reverse = sort_order == "desc"
    if sort_by == "created_at":
        results.sort(key=lambda x: _field(x, "created_at", datetime.min), reverse=reverse)
    elif sort_by in ["total_return", "sharpe_ratio", "max_drawdown"]:
        results.sort(key=lambda x: _field(x, sort_by, 0.0), reverse=reverse)

    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_results = results[start:end]

    normalized_backtests: list[dict[str, Any]] = []
    for item in paginated_results:
        if isinstance(item, dict):
            payload = dict(item)
        elif hasattr(item, "model_dump"):
            payload = item.model_dump(mode="json")
        else:
            from fastapi.encoders import jsonable_encoder

            payload = jsonable_encoder(item)

        display_name = _resolve_strategy_display_name(payload)
        if display_name:
            payload["strategy_display_name"] = display_name
            normalized_strategy_name = _normalize_strategy_key(payload.get("strategy_name"))
            if normalized_strategy_name and normalized_strategy_name.lower() in {
                "topkdropout",
                "weightstrategy",
            }:
                payload["strategy_name"] = display_name

        normalized_backtests.append(payload)

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "backtests": normalized_backtests,
    }


@router.delete("/results/{backtest_id}")
async def delete_backtest(
    request: Request,
    backtest_id: str,
    user_id: str | None = Query(None, description="用户ID（已废弃，自动使用认证身份）"),
    tenant_id: str | None = Query(None, description="租户ID（已废弃，自动使用认证身份）"),
    service: Any = Depends(get_qlib_service),
) -> dict[str, str]:
    """删除回测记录"""
    auth_user_id, auth_tenant_id = _identity_from_request(
        request,
        provided_user_id=user_id,
        provided_tenant_id=tenant_id,
    )
    success = await service.delete_backtest(backtest_id, auth_user_id, auth_tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="回测记录不存在或无权删除")
    return {"message": "删除成功", "backtest_id": backtest_id}


@router.get("/compare/{id1}/{id2}")
async def compare_backtests(
    request: Request,
    id1: str,
    id2: str,
    user_id: str | None = Query(None, description="用户ID（已废弃，自动使用认证身份）"),
    tenant_id: str | None = Query(None, description="租户ID（已废弃，自动使用认证身份）"),
    service: Any = Depends(get_qlib_service),
) -> dict[str, Any]:
    """对比两个回测结果"""
    try:
        auth_user_id, auth_tenant_id = _identity_from_request(
            request,
            provided_user_id=user_id,
            provided_tenant_id=tenant_id,
        )
        result = await service.compare_backtests(id1, id2, auth_user_id, auth_tenant_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"对比失败: {str(e)}")


@router.get("/backtest/{backtest_id}/status")
async def get_backtest_status(
    request: Request,
    backtest_id: str,
    tenant_id: str | None = Query(None, description="租户ID（已废弃，自动使用认证身份）"),
    service: Any = Depends(get_qlib_service),
) -> dict[str, Any]:
    """获取回测状态"""
    auth_user_id, auth_tenant_id = _identity_from_request(request, provided_tenant_id=tenant_id)
    status = await service.get_status(
        backtest_id,
        tenant_id=auth_tenant_id,
        user_id=auth_user_id,
    )

    if status:
        return status

    raise HTTPException(status_code=404, detail="回测任务不存在")
