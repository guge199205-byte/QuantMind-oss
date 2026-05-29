"""RD-Agent 因子管理 REST API"""

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.services.engine.qlib_app.services.rd_agent_persistence import (
    RDAgentFactorPersistence,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rd-agent", tags=["RD-Agent"])
persistence = RDAgentFactorPersistence()

# 跟踪在跑的轻量回测，防止重复触发
_running_backtests: set[str] = set()


@router.get("/factors")
async def list_factors(
    user_id: Optional[str] = Query(None, description="按用户过滤"),
    status: Optional[str] = Query(None, description="按状态过滤: pending/backtesting/completed/failed"),
    limit: int = Query(50, ge=1, le=200),
):
    """列出所有已生成的因子"""
    factors = await persistence.list_factors(user_id=user_id, status=status, limit=limit)
    return {"code": 200, "data": {"factors": factors, "total": len(factors)}}


@router.get("/factors/{factor_id}")
async def get_factor(factor_id: str):
    """获取单个因子详情"""
    factor = await persistence.get_factor(factor_id)
    if not factor:
        raise HTTPException(status_code=404, detail=f"Factor {factor_id} not found")
    return {"code": 200, "data": factor}


@router.post("/factors/{factor_id}/backtest")
async def backtest_factor(
    factor_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """对 RD-Agent 因子发起轻量验证（异步跑 IC/夏普，回填到因子表）"""
    factor = await persistence.get_factor(factor_id)
    if not factor:
        raise HTTPException(status_code=404, detail=f"Factor {factor_id} not found")

    if not factor.get("factor_code"):
        raise HTTPException(status_code=400, detail="因子代码为空，无法回测")

    if factor_id in _running_backtests:
        return {
            "code": 200,
            "data": {
                "factor_id": factor_id,
                "status": "backtesting",
                "message": "回测已在进行中",
            },
        }

    await persistence.update_factor_metrics(factor_id, status="backtesting")
    _running_backtests.add(factor_id)

    # 后台异步执行，避免接口阻塞
    asyncio.create_task(
        _run_lightweight_backtest(factor_id, factor.get("factor_code") or "", start_date, end_date)
    )

    return {
        "code": 200,
        "data": {
            "factor_id": factor_id,
            "status": "backtesting",
            "message": f"快速验证已触发: {factor.get('factor_name')}",
        },
    }


async def _run_lightweight_backtest(
    factor_id: str,
    factor_code: str,
    start_date: Optional[str],
    end_date: Optional[str],
) -> None:
    """轻量回测：execfile 因子代码 → 用 Qlib 数据算 IC/夏普回填"""
    try:
        import numpy as np
        import pandas as pd
        from qlib.data import D

        # 1) 加载因子代码，找出 Factor 类
        ns: dict[str, Any] = {}
        exec(compile(factor_code, f"<rd-factor-{factor_id}>", "exec"), ns)

        factor_cls = None
        for v in ns.values():
            if isinstance(v, type) and hasattr(v, "__call__") and v.__module__ == "builtins":
                if getattr(v, "name", None) or v.__name__.lower().endswith("factor"):
                    factor_cls = v
                    break
        if factor_cls is None:
            raise RuntimeError("因子代码中未找到可调用的 Factor 类")

        # 2) 取 1 年沪深 300 数据做样本
        end = end_date or "2024-12-31"
        start = start_date or "2024-01-01"
        instruments = D.instruments(market="csi300")
        fields = ["$open", "$high", "$low", "$close", "$volume", "$factor"]
        df = D.features(instruments, fields, start_time=start, end_time=end, freq="day")
        if df.empty:
            raise RuntimeError("Qlib 数据为空，请检查 QLIB_PROVIDER_URI")

        # 3) 跑因子
        factor_inst = factor_cls()
        sample_codes = df.index.get_level_values(0).unique()[:50]
        ic_list: list[float] = []
        ret_list: list[float] = []

        for code in sample_codes:
            sub = df.xs(code, level=0).copy()
            if len(sub) < 30:
                continue
            try:
                fv = factor_inst(sub)
                fv_col = fv.iloc[:, 0] if hasattr(fv, "iloc") else pd.Series(fv)
            except Exception:
                continue
            fwd_ret = sub["$close"].pct_change(5).shift(-5)
            paired = pd.concat([fv_col, fwd_ret], axis=1).dropna()
            if len(paired) < 10:
                continue
            ic = paired.iloc[:, 0].corr(paired.iloc[:, 1])
            if np.isfinite(ic):
                ic_list.append(float(ic))
            # 简单分组：因子 top 30% 等权多头
            cutoff = fv_col.quantile(0.7)
            longs = fwd_ret[fv_col >= cutoff].dropna()
            if len(longs) > 0:
                ret_list.append(float(longs.mean()))

        if not ic_list:
            raise RuntimeError("所有股票都无法计算 IC，因子可能与数据列不匹配")

        ic_mean = float(np.mean(ic_list))
        sharpe = (
            float(np.mean(ret_list) / (np.std(ret_list) + 1e-8) * np.sqrt(252))
            if ret_list else None
        )
        annual_return = float(np.mean(ret_list) * 252) if ret_list else None

        await persistence.update_factor_metrics(
            factor_id,
            status="completed",
            ic_value=ic_mean,
            sharpe_ratio=sharpe,
            annual_return=annual_return,
        )
        logger.info(
            "[rd-backtest] %s done ic=%.4f sharpe=%s",
            factor_id, ic_mean, f"{sharpe:.3f}" if sharpe is not None else "N/A",
        )

    except Exception as exc:
        logger.exception("[rd-backtest] %s failed", factor_id)
        try:
            await persistence.update_factor_metrics(
                factor_id,
                status="failed",
                metadata={"backtest_error": str(exc)[:500]},
            )
        except Exception:
            pass
    finally:
        _running_backtests.discard(factor_id)


@router.get("/stats")
async def get_stats():
    """RD-Agent 因子统计信息"""
    from backend.shared.database_manager_v2 import get_session
    from sqlalchemy import text

    async with get_session(read_only=True) as session:
        rows = await session.execute(text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE status = 'backtesting') AS backtesting,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                AVG(ic_value) FILTER (WHERE ic_value IS NOT NULL) AS avg_ic,
                AVG(sharpe_ratio) FILTER (WHERE sharpe_ratio IS NOT NULL) AS avg_sharpe,
                MAX(ic_value) AS best_ic,
                MAX(sharpe_ratio) AS best_sharpe
            FROM rd_agent_factors
        """))
        row = rows.mappings().first()

    if not row:
        return {"code": 200, "data": {}}

    data = dict(row)
    for key in ("avg_ic", "best_ic", "avg_sharpe", "best_sharpe"):
        if data.get(key) is not None:
            data[key] = round(float(data[key]), 4)
    return {"code": 200, "data": data}
