"""AlphaAgent / RD-Agent 因子挖掘 REST API

支持多市场因子挖掘: A股、加密货币、港股、美股
"""

import asyncio
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from backend.services.engine.alpha_agent.launcher import get_launcher
from backend.services.engine.qlib_app.services.rd_agent_persistence import (
    RDAgentFactorPersistence,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/alpha-agent", tags=["AlphaAgent"])
persistence = RDAgentFactorPersistence()

_running_backtests: set[str] = set()


@router.get("/markets")
async def list_markets():
    """列出所有可用的市场"""
    from backend.services.engine.rd_agent.market_adapters import list_markets as _list_markets
    markets = _list_markets()
    # Check data readiness for each market
    for m in markets:
        try:
            from backend.services.engine.rd_agent.market_adapters import get_adapter
            adapter = get_adapter(m["market_id"])
            m["data_ready"] = adapter.is_data_ready()
        except Exception:
            m["data_ready"] = False
    return {"code": 200, "data": {"markets": markets, "total": len(markets)}}


@router.post("/evolve")
async def start_evolution(
    user_id: str = Query(..., description="用户 ID"),
    market: str = Query("a_share", description="市场: a_share, crypto, hong_kong, us_stock"),
    loop_n: int = Query(3, ge=1, le=20, description="演化轮数"),
    direction: str = Query("", description="因子挖掘方向/假设"),
    data_source: str = Query("", description="数据源: qlib_bin, parquet, pg (留空使用默认)"),
):
    """启动因子演化任务"""
    # Validate market
    try:
        from backend.services.engine.rd_agent.market_adapters import get_adapter, list_markets
        adapter = get_adapter(market)
    except ValueError:
        available = [m["market_id"] for m in list_markets()]
        raise HTTPException(
            status_code=400,
            detail=f"Unknown market: {market}. Available: {available}",
        )

    api_key = (
        os.getenv("AI_IDE_LLM_API_KEY")
        or os.getenv("AI_IDE_API_KEY")
        or os.getenv("OPENAI_API_KEY", "")
    )
    if not api_key or "mock-api-key" in api_key:
        raise HTTPException(
            status_code=500,
            detail="API Key 未配置。请先在个人中心配置 API Key 后再使用因子挖掘功能。",
        )

    launcher = get_launcher()
    task_id = await launcher.start_evolution(
        user_id,
        market=market,
        loop_n=loop_n,
        direction=direction or None,
        data_source=data_source or None,
    )
    return {
        "code": 200,
        "data": {
            "task_id": task_id,
            "market": market,
            "market_name": adapter.market_name,
            "status": "pending",
            "message": f"{adapter.market_name} 因子挖掘任务已启动",
        },
    }


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """查询演化任务状态"""
    launcher = get_launcher()
    status = await launcher.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return {"code": 200, "data": status}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消演化任务"""
    launcher = get_launcher()
    ok = await launcher.cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail="无法取消任务（可能已完成或不存在）")
    return {"code": 200, "data": {"task_id": task_id, "status": "cancelled"}}


@router.get("/tasks/{task_id}/log")
async def get_task_log(
    task_id: str,
    tail: int = Query(500, ge=1, le=5000, description="返回最后N行"),
    offset: int = Query(0, ge=0, description="从第N行开始返回"),
):
    """获取任务的详细子进程日志（实时监控用）"""
    launcher = get_launcher()
    log_content = await launcher.get_task_log(task_id, tail=tail + offset)
    if log_content is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} log not found")
    lines = log_content.splitlines()
    if offset > 0:
        lines = lines[offset:]
    return {
        "code": 200,
        "data": {
            "task_id": task_id,
            "lines": lines,
            "total": len(lines),
        },
    }


@router.get("/tasks")
async def list_tasks(
    user_id: Optional[str] = Query(None, description="按用户过滤"),
    market: Optional[str] = Query(None, description="按市场过滤"),
):
    """列出所有演化任务"""
    launcher = get_launcher()
    tasks = await launcher.list_tasks(user_id=user_id)
    if market:
        tasks = [t for t in tasks if t.get("market") == market]
    return {"code": 200, "data": {"tasks": tasks, "total": len(tasks)}}


@router.get("/factors")
async def list_factors(
    user_id: Optional[str] = Query(None, description="按用户过滤"),
    market: Optional[str] = Query(None, description="按市场过滤"),
    status: Optional[str] = Query(None, description="按状态过滤: pending/backtesting/completed/failed"),
    limit: int = Query(50, ge=1, le=200),
):
    """列出所有已生成的因子"""
    factors = await persistence.list_factors(user_id=user_id, status=status, limit=limit)
    if market:
        factors = [f for f in factors if f.get("metadata", {}).get("market") == market]
    return {"code": 200, "data": {"factors": factors, "total": len(factors)}}


@router.get("/factors/{factor_id}")
async def get_factor(factor_id: str):
    """获取单个因子详情"""
    factor = await persistence.get_factor(factor_id)
    if not factor:
        raise HTTPException(status_code=404, detail=f"Factor {factor_id} not found")
    return {"code": 200, "data": factor}


@router.post("/factors/{factor_id}/explain")
async def explain_factor(factor_id: str):
    """用 LLM 中文解释因子含义"""
    factor = await persistence.get_factor(factor_id)
    if not factor:
        raise HTTPException(status_code=404, detail=f"Factor {factor_id} not found")

    # Check if explanation already exists
    metadata = factor.get("metadata") or {}
    if metadata.get("explanation"):
        return {"code": 200, "data": {"explanation": metadata["explanation"], "cached": True}}

    factor_name = factor.get("factor_name", "unknown")
    factor_code = factor.get("factor_code", "")
    factor_formulation = metadata.get("factor_formulation", "")

    # Call LLM for explanation
    import httpx

    api_key = (
        os.getenv("AI_IDE_LLM_API_KEY")
        or os.getenv("AI_IDE_API_KEY")
        or os.getenv("OPENAI_API_KEY", "")
    )
    api_base = (
        os.getenv("OPENAI_BASE_URL")
        or os.getenv("OPENAI_API_BASE")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    model = os.getenv("CHAT_MODEL", "deepseek-v3")

    if not api_key:
        raise HTTPException(status_code=500, detail="API Key 未配置")

    prompt = f"""请用中文简洁地解释以下量化因子。输出格式：
1. **含义**：一句话概括
2. **金融直觉**：为什么这个因子可能有效
3. **适用场景**：在什么市场环境下表现较好
4. **预期方向**：因子值高/低时预示什么

因子名称：{factor_name}
因子公式：{factor_formulation or factor_code[:500]}

请直接输出解释，不要重复因子公式。"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{api_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            explanation = resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("LLM explain failed: %s", e)
        raise HTTPException(status_code=500, detail=f"LLM 解释失败: {str(e)[:200]}")

    # Store explanation in metadata
    metadata["explanation"] = explanation
    await persistence.update_factor_metrics(factor_id, metadata=metadata)

    return {"code": 200, "data": {"explanation": explanation, "cached": False}}


@router.post("/factors/{factor_id}/backtest")
async def backtest_factor(
    factor_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """对因子发起轻量验证"""
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


@router.post("/factors/{factor_id}/export")
async def export_factor_to_ide(
    factor_id: str,
    request: Request,
):
    """将因子代码导出到 AI-IDE 工作空间"""
    # 从请求中获取用户 ID
    user = getattr(request.state, "user", None)
    user_id = str(user.get("user_id") or user.get("sub") or "") if user else ""
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    factor = await persistence.get_factor(factor_id)
    if not factor:
        raise HTTPException(status_code=404, detail=f"Factor {factor_id} not found")

    factor_code = factor.get("factor_code") or ""
    if not factor_code.strip():
        raise HTTPException(status_code=400, detail="因子代码为空，无法导出")

    factor_name = factor.get("factor_name", "unnamed_factor")
    meta = factor.get("metadata") or {}

    # 生成带头部注释的完整 Python 文件
    header_lines = [
        f'"""',
        f'Factor: {factor_name}',
        f'Source: RD-Agent Alpha Research',
        f'IC: {factor.get("ic_value", "N/A")}',
        f'RankIC: {meta.get("rank_ic", "N/A")}',
        f'Sharpe: {factor.get("sharpe_ratio", "N/A")}',
        f'Market: {meta.get("market", "a_share")}',
        f'Description: {meta.get("description", "")[:200]}',
        f'"""',
        f'',
    ]
    full_code = "\n".join(header_lines) + factor_code

    # 保存到策略库
    from backend.shared.strategy_storage import get_strategy_storage_service
    svc = get_strategy_storage_service()
    file_name = f"factor_{factor_name}"
    res = await svc.save(
        user_id=user_id,
        name=file_name,
        code=full_code,
        metadata={
            "status": "DRAFT",
            "source": "alpha_research",
            "factor_id": factor_id,
            "description": f"Alpha Factor: {factor_name}",
            "tags": ["alpha", meta.get("market", "a_share")],
        },
    )

    return {
        "code": 200,
        "data": {
            "strategy_id": res["id"],
            "name": file_name,
            "message": f"因子 {factor_name} 已导出到 AI-IDE 工作空间",
        },
    }


@router.get("/stats")
async def get_stats(
    market: Optional[str] = Query(None, description="按市场过滤统计"),
):
    """因子统计信息"""
    from backend.shared.database_manager_v2 import get_session
    from sqlalchemy import text

    where_clause = ""
    if market:
        where_clause = "WHERE metadata->>'market' = :market"

    async with get_session(read_only=True) as session:
        params = {"market": market} if market else {}
        rows = await session.execute(text(f"""
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
            {where_clause}
        """), params)
        row = rows.mappings().first()

    if not row:
        return {"code": 200, "data": {}}

    data = dict(row)
    for key in ("avg_ic", "best_ic", "avg_sharpe", "best_sharpe"):
        if data.get(key) is not None:
            data[key] = round(float(data[key]), 4)
    return {"code": 200, "data": data}


async def _run_lightweight_backtest(
    factor_id: str,
    factor_code: str,
    start_date: Optional[str],
    end_date: Optional[str],
) -> None:
    """轻量回测"""
    try:
        import numpy as np
        import pandas as pd
        from qlib.data import D

        ns: dict = {}
        exec(compile(factor_code, f"<alpha-factor-{factor_id}>", "exec"), ns)

        factor_cls = None
        for v in ns.values():
            if isinstance(v, type) and hasattr(v, "__call__") and v.__module__ == "builtins":
                if getattr(v, "name", None) or v.__name__.lower().endswith("factor"):
                    factor_cls = v
                    break
        if factor_cls is None:
            raise RuntimeError("因子代码中未找到可调用的 Factor 类")

        end = end_date or "2024-12-31"
        start = start_date or "2024-01-01"
        instruments = D.instruments(market="csi300")
        fields = ["$open", "$high", "$low", "$close", "$volume", "$factor"]
        df = D.features(instruments, fields, start_time=start, end_time=end, freq="day")
        if df.empty:
            raise RuntimeError("Qlib 数据为空，请检查 QLIB_PROVIDER_URI")

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
            "[alpha-backtest] %s done ic=%.4f sharpe=%s",
            factor_id, ic_mean, f"{sharpe:.3f}" if sharpe is not None else "N/A",
        )

    except Exception as exc:
        logger.exception("[alpha-backtest] %s failed", factor_id)
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
