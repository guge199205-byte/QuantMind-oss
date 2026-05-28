"""
管理员 - 数据平台路由
========================

GET  /api/v1/admin/data-platform/markets                 列出支持的市场
GET  /api/v1/admin/data-platform/sources                 列出所有已注册数据源
GET  /api/v1/admin/data-platform/sources/{name}/health   单源所有字段健康
GET  /api/v1/admin/data-platform/health-matrix?market=A  市场 × 字段 × 源 健康矩阵
GET  /api/v1/admin/data-platform/field-coverage          字段覆盖表（YAML 路由 + 实际可用）
GET  /api/v1/admin/data-platform/quality-alerts          告警列表（分页 + 过滤）
POST /api/v1/admin/data-platform/quality-alerts/{id}/ack 标记告警已处理
POST /api/v1/admin/data-platform/sources/{name}/sync     触发指定源同步（占位）
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.services.api.user_app.middleware.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_routing():
    """延迟引入 data_platform，避免 API 启动时强依赖 engine 模块。"""
    from backend.services.engine.data_platform.aggregator import FieldRoutingTable
    return FieldRoutingTable()


def _get_registry():
    from backend.services.engine.data_platform.adapters import register_all
    from backend.services.engine.data_platform.registry import get_registry
    register_all()
    return get_registry()


def _get_monitor():
    from backend.services.engine.data_platform.monitor import get_monitor
    try:
        import redis  # type: ignore
        url = os.getenv("REDIS_URL", "redis://quantmind-redis:6379/0")
        client = redis.from_url(url, socket_timeout=2)
        return get_monitor(redis_client=client)
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis init failed, falling back to in-memory monitor: %s", exc)
        return get_monitor()


def _db_engine():
    from sqlalchemy import create_engine
    from urllib.parse import quote_plus as _q
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        host = os.getenv("DB_MASTER_HOST", "quantmind-db")
        port = os.getenv("DB_MASTER_PORT", "5432")
        user = os.getenv("DB_USER", "quantmind")
        pwd = _q(os.getenv("DB_PASSWORD", "quantmind"))
        name = os.getenv("DB_NAME", "quantmind")
        db_url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"
    elif "asyncpg" in db_url:
        db_url = db_url.replace("asyncpg", "psycopg2")
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(db_url, pool_pre_ping=True)


# ---------------------------------------------------------------------------
@router.get("/markets")
async def list_markets(current_user: dict = Depends(require_admin)):
    try:
        rt = _get_routing()
        return {
            "success": True,
            "data": {
                "markets": rt.list_markets(),
                "timestamp": _now_iso(),
            },
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


@router.get("/sources")
async def list_sources(current_user: dict = Depends(require_admin)):
    try:
        rt = _get_routing()
        reg = _get_registry()
        monitor = _get_monitor()
        out: list[dict[str, Any]] = []
        for name in reg.list_sources():
            adapter = reg.get(name)
            # 统计该源覆盖的字段（去重）
            covered_fields: set[str] = set()
            for m in rt.list_markets():
                for f in rt.list_fields(m):
                    route = rt.get_route(m, f)
                    if name in route.ordered_sources and adapter.supports(f, m):
                        covered_fields.add(f)
            # 用 daily_kline 作为代表抓 health 摘要
            health = monitor.get_health(name, "daily_kline")
            out.append({
                "name": name,
                "class": adapter.__class__.__name__,
                "markets": adapter.markets,
                "field_count": len(adapter.fields),
                "covered_field_count": len(covered_fields),
                "health_summary": {
                    "last_success_at": health.get("last_success_at"),
                    "last_error_at": health.get("last_error_at"),
                    "last_error_msg": health.get("last_error_msg"),
                    "error_rate_1h": health.get("error_rate_1h"),
                    "avg_latency_ms": health.get("avg_latency_ms"),
                },
            })
        return {"success": True, "data": {"sources": out, "timestamp": _now_iso()}}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


@router.get("/sources/{name}/health")
async def source_health(
    name: str,
    current_user: dict = Depends(require_admin),
):
    try:
        rt = _get_routing()
        monitor = _get_monitor()
        per_field: dict[str, Any] = {}
        for m in rt.list_markets():
            for f in rt.list_fields(m):
                route = rt.get_route(m, f)
                if name not in route.ordered_sources:
                    continue
                per_field[f"{m}/{f}"] = monitor.get_health(name, f)
        return {
            "success": True,
            "data": {
                "source": name,
                "fields": per_field,
                "timestamp": _now_iso(),
            },
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


@router.get("/health-matrix")
async def health_matrix(
    market: str = Query("A", description="A / HK / US"),
    current_user: dict = Depends(require_admin),
):
    """字段 × 源 健康矩阵，前端用来渲染颜色 grid。"""
    try:
        rt = _get_routing()
        monitor = _get_monitor()
        reg = _get_registry()
        m = market.upper()
        fields = rt.list_fields(m)
        sources_seen: set[str] = set()
        cells: list[dict[str, Any]] = []
        for f in fields:
            route = rt.get_route(m, f)
            for src in route.ordered_sources:
                sources_seen.add(src)
                health = monitor.get_health(src, f)
                registered = src in reg.list_sources()
                cells.append({
                    "field": f,
                    "source": src,
                    "is_primary": src == route.primary,
                    "registered": registered,
                    "last_success_at": health.get("last_success_at"),
                    "last_error_at": health.get("last_error_at"),
                    "error_rate_1h": float(health.get("error_rate_1h", 0) or 0),
                    "avg_latency_ms": float(health.get("avg_latency_ms", 0) or 0),
                    "fallback_triggered_count": int(health.get("fallback_triggered_count", 0) or 0),
                })
        return {
            "success": True,
            "data": {
                "market": m,
                "fields": fields,
                "sources": sorted(sources_seen),
                "cells": cells,
                "timestamp": _now_iso(),
            },
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


@router.get("/field-coverage")
async def field_coverage(current_user: dict = Depends(require_admin)):
    """所有市场 × 字段 × (primary, fallbacks, consensus, cleanup, tier)。"""
    try:
        rt = _get_routing()
        out: dict[str, list[dict[str, Any]]] = {}
        for m in rt.list_markets():
            rows = []
            for f in rt.list_fields(m):
                r = rt.get_route(m, f)
                rows.append({
                    "field": f,
                    "tier": r.tier,
                    "primary": r.primary,
                    "fallbacks": r.fallbacks,
                    "consensus": r.consensus,
                    "cleanup": r.cleanup,
                })
            out[m] = rows
        return {"success": True, "data": {"coverage": out, "timestamp": _now_iso()}}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


# ---------------------------------------------------------------------------
# 告警
# ---------------------------------------------------------------------------
class AckRequest(BaseModel):
    note: Optional[str] = None


@router.get("/quality-alerts")
async def list_quality_alerts(
    severity: Optional[str] = None,
    market: Optional[str] = None,
    field: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_admin),
):
    from sqlalchemy import text as sql_text
    try:
        engine = _db_engine()
        clauses = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if severity:
            clauses.append("severity = :severity")
            params["severity"] = severity
        if market:
            clauses.append("market = :market")
            params["market"] = market.upper()
        if field:
            clauses.append("field = :field")
            params["field"] = field
        if acknowledged is not None:
            clauses.append("acknowledged = :ack")
            params["ack"] = bool(acknowledged)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with engine.begin() as conn:
            total = conn.execute(
                sql_text(f"SELECT COUNT(*) FROM data_quality_alerts {where}"),
                params,
            ).scalar() or 0
            rows = conn.execute(
                sql_text(
                    f"""
                    SELECT id, alert_type, severity, market, field, source, symbol,
                           trade_date, message, details, acknowledged, acknowledged_by,
                           acknowledged_at, created_at
                    FROM data_quality_alerts
                    {where}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).fetchall()
        items = [
            {
                "id": r[0], "alert_type": r[1], "severity": r[2],
                "market": r[3], "field": r[4], "source": r[5], "symbol": r[6],
                "trade_date": r[7].isoformat() if r[7] else None,
                "message": r[8], "details": r[9],
                "acknowledged": bool(r[10]),
                "acknowledged_by": r[11],
                "acknowledged_at": r[12].isoformat() if r[12] else None,
                "created_at": r[13].isoformat() if r[13] else None,
            }
            for r in rows
        ]
        return {
            "success": True,
            "data": {"total": total, "items": items, "timestamp": _now_iso()},
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("list_quality_alerts failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


@router.post("/quality-alerts/{alert_id}/ack")
async def ack_quality_alert(
    alert_id: int,
    payload: AckRequest = AckRequest(),  # body 可空
    current_user: dict = Depends(require_admin),
):
    from sqlalchemy import text as sql_text
    try:
        user_id = str(current_user.get("user_id") or current_user.get("id") or "admin")
        engine = _db_engine()
        with engine.begin() as conn:
            updated = conn.execute(
                sql_text(
                    """
                    UPDATE data_quality_alerts
                    SET acknowledged = TRUE,
                        acknowledged_by = :uid,
                        acknowledged_at = NOW()
                    WHERE id = :id
                    """
                ),
                {"uid": user_id, "id": alert_id},
            ).rowcount
        if not updated:
            raise HTTPException(status_code=404, detail=f"alert {alert_id} not found")
        return {"success": True, "data": {"alert_id": alert_id, "acknowledged_by": user_id}}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


# ---------------------------------------------------------------------------
# 同步触发（占位，D8 cron 接入）
# ---------------------------------------------------------------------------
class SyncRequest(BaseModel):
    market: str = "A"
    field: str = "daily_kline"
    symbols: list[str] = []


@router.post("/sources/{name}/sync")
async def trigger_sync(
    name: str,
    payload: SyncRequest,
    current_user: dict = Depends(require_admin),
):
    """触发指定数据源对若干 symbol 的拉取（同步执行；MVP 阶段串行）。"""
    try:
        rt = _get_routing()
        reg = _get_registry()
        if name not in reg.list_sources():
            raise HTTPException(status_code=404, detail=f"source {name} not registered")
        try:
            route = rt.get_route(payload.market, payload.field)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if name not in route.ordered_sources:
            raise HTTPException(
                status_code=400,
                detail=f"{name} not configured for {payload.market}/{payload.field}",
            )

        from backend.services.engine.data_platform.aggregator import FieldAggregator
        from backend.services.engine.data_platform.cleaner import DataCleaner
        agg = FieldAggregator(
            registry=reg, routing=rt, monitor=_get_monitor(), cleaner=DataCleaner(),
        )

        results: list[dict[str, Any]] = []
        for sym in payload.symbols[:50]:  # 限制 batch
            try:
                res = agg.fetch(
                    market=payload.market, field=payload.field, symbol=sym,
                )
                results.append({
                    "symbol": sym, "ok": True,
                    "source_used": res.source_used, "rows": len(res.data),
                    "cleaning": res.cleaning_report,
                })
            except Exception as exc:  # noqa: BLE001
                results.append({"symbol": sym, "ok": False, "error": str(exc)})
        return {"success": True, "data": {"source": name, "results": results}}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


# ---------------------------------------------------------------------------
# 一键同步：对当前 market 的所有声明源依次触发同一组 symbols
# ---------------------------------------------------------------------------
class SweepRequest(BaseModel):
    market: str = "A"
    field: str = "daily_kline"
    symbols: list[str] = []
    include_fallbacks: bool = True


@router.post("/sweep")
async def sweep_market(
    payload: SweepRequest,
    current_user: dict = Depends(require_admin),
):
    """
    对 market×field 路由声明的所有源（primary + 可选 fallbacks）依次触发一次 fetch。

    用途：刚部署或长期未运行时，手动点亮"健康矩阵"——让监控里有真实的成功/错误样本。
    单次最多 20 个 symbol，串行执行；返回每个 source × symbol 的结果摘要。
    """
    try:
        rt = _get_routing()
        reg = _get_registry()
        try:
            route = rt.get_route(payload.market, payload.field)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        sources: list[str] = [route.primary]
        if payload.include_fallbacks:
            sources.extend([s for s in (route.fallbacks or []) if s not in sources])
        sources = [s for s in sources if s in reg.list_sources()]
        if not sources:
            raise HTTPException(
                status_code=400,
                detail=f"{payload.market}/{payload.field} 路由源均未注册",
            )

        from backend.services.engine.data_platform.aggregator import FieldAggregator
        from backend.services.engine.data_platform.cleaner import DataCleaner
        from datetime import date, timedelta

        monitor = _get_monitor()
        agg = FieldAggregator(
            registry=reg, routing=rt, monitor=monitor, cleaner=DataCleaner(),
        )

        symbols = [s.strip() for s in payload.symbols if s and s.strip()][:20]
        if not symbols:
            raise HTTPException(status_code=400, detail="symbols 不能为空")

        end = date.today()
        start = end - timedelta(days=14)

        per_source: list[dict[str, Any]] = []
        ok_total = 0
        fail_total = 0
        for src in sources:
            adapter = reg.get(src)
            sym_results: list[dict[str, Any]] = []
            for sym in symbols:
                t0 = _now_iso()
                try:
                    df = None
                    if hasattr(adapter, "fetch_field"):
                        try:
                            df = adapter.fetch_field(
                                payload.field, sym, start=start, end=end,
                            )
                        except (NotImplementedError, Exception) as field_exc:
                            # fetch_field 未实现该字段，回退到 fetch_daily
                            msg = str(field_exc).lower()
                            if ("not implemented" in msg or "未实现" in msg
                                    or isinstance(field_exc, NotImplementedError)):
                                df = None
                            else:
                                raise
                    if df is None and hasattr(adapter, "fetch_daily"):
                        df = adapter.fetch_daily(sym, start, end)
                    rows = 0 if df is None else len(df)
                    monitor.record_success(src, payload.field, latency_ms=0.0)
                    sym_results.append({"symbol": sym, "ok": True, "rows": rows, "started": t0})
                    ok_total += 1
                except Exception as exc:  # noqa: BLE001
                    monitor.record_error(src, payload.field, error=str(exc))
                    sym_results.append({"symbol": sym, "ok": False, "error": str(exc)[:200], "started": t0})
                    fail_total += 1
            per_source.append({"source": src, "results": sym_results})

        # 顺便走一次聚合：让"主源 + cleanup + consensus"链路也被记录
        agg_results: list[dict[str, Any]] = []
        for sym in symbols:
            try:
                res = agg.fetch(
                    market=payload.market, field=payload.field, symbol=sym,
                    start=start, end=end,
                )
                agg_results.append({
                    "symbol": sym, "ok": True,
                    "source_used": res.source_used,
                    "consensus_sources": res.consensus_sources,
                    "rows": len(res.data),
                })
            except Exception as exc:  # noqa: BLE001
                agg_results.append({"symbol": sym, "ok": False, "error": str(exc)[:200]})

        return {
            "success": True,
            "data": {
                "market": payload.market,
                "field": payload.field,
                "sources": sources,
                "symbols": symbols,
                "summary": {"ok": ok_total, "failed": fail_total},
                "per_source": per_source,
                "aggregated": agg_results,
                "timestamp": _now_iso(),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


# ---------------------------------------------------------------------------
# 日常数据同步管理
# ---------------------------------------------------------------------------
class DailySyncRequest(BaseModel):
    market: str = "A"
    symbols: list[str] = []
    incremental: bool = True
    calibrate: bool = True


@router.post("/daily-sync")
async def trigger_daily_sync(
    payload: DailySyncRequest,
    current_user: dict = Depends(require_admin),
):
    """异步提交统一数据同步任务到 Celery，立即返回 task_id。"""
    try:
        from backend.services.engine.tasks.celery_tasks import daily_data_sync_task

        symbols_str = ",".join(payload.symbols) if payload.symbols else ""
        task = daily_data_sync_task.delay(
            market=payload.market,
            symbols=symbols_str,
            incremental=payload.incremental,
            calibrate=payload.calibrate,
        )
        return {
            "success": True,
            "data": {
                "task_id": task.id,
                "status": "submitted",
                "message": f"同步任务已提交 (task_id={task.id})，后台执行中",
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("daily_sync submit failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


@router.get("/daily-sync/status/{task_id}")
async def get_daily_sync_task_status(
    task_id: str,
    current_user: dict = Depends(require_admin),
):
    """查询 Celery 异步同步任务的状态和结果。"""
    try:
        from celery.result import AsyncResult
        from backend.services.engine.tasks.celery_tasks import celery_app

        result = AsyncResult(task_id, app=celery_app)
        resp: dict[str, Any] = {
            "task_id": task_id,
            "status": result.status,  # PENDING / STARTED / SUCCESS / FAILURE
        }
        if result.ready():
            if result.successful():
                resp["result"] = result.get()
            else:
                resp["error"] = str(result.result)
                resp["traceback"] = result.traceback
        else:
            info = result.info or {}
            if isinstance(info, dict):
                resp["progress"] = info
        return {"success": True, "data": resp}
    except Exception as exc:  # noqa: BLE001
        logger.error("task status query failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


@router.get("/sync-status")
async def get_sync_status(current_user: dict = Depends(require_admin)):
    """获取当前数据同步状态摘要。"""
    try:
        import asyncio
        from backend.scripts.daily_data_sync import get_sync_status

        loop = asyncio.get_event_loop()
        status = await loop.run_in_executor(None, get_sync_status)
        return {"success": True, "data": status}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


@router.post("/update-investment-data")
async def update_investment_data_endpoint(
    version: str = "",
    current_user: dict = Depends(require_admin),
):
    """下载最新 investment_data qlib_bin 并解压更新。"""
    try:
        import asyncio
        import functools
        from backend.scripts.daily_data_sync import update_investment_data

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, functools.partial(update_investment_data, version=version)
        )
        return {"success": True, "data": result}
    except Exception as exc:  # noqa: BLE001
        logger.error("update_investment_data failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


# ---------------------------------------------------------------------------
# 数据新鲜度
# ---------------------------------------------------------------------------
@router.get("/freshness")
async def get_freshness(
    market: str = Query("A", description="A / HK / US"),
    current_user: dict = Depends(require_admin),
):
    """按市场返回每个源×字段的数据新鲜度（最后成功时间距今天数）。"""
    try:
        from datetime import date as _date, datetime as _dt

        rt = _get_routing()
        monitor = _get_monitor()
        reg = _get_registry()
        m = market.upper()

        now = _dt.now(timezone.utc)
        today = _date.today()
        items: list[dict[str, Any]] = []

        for f in rt.list_fields(m):
            route = rt.get_route(m, f)
            all_sources = [route.primary] + [s for s in (route.fallbacks or []) if s != route.primary]
            for src in all_sources:
                if src not in reg.list_sources():
                    continue
                health = monitor.get_health(src, f)
                last_ok = health.get("last_success_at")
                days_stale = None
                freshness = "unknown"
                if last_ok:
                    try:
                        last_dt = _dt.fromisoformat(last_ok.replace("Z", "+00:00"))
                        days_stale = (now - last_dt).days
                        if days_stale == 0:
                            freshness = "fresh"
                        elif days_stale <= 3:
                            freshness = "stale"
                        else:
                            freshness = "outdated"
                    except Exception:
                        pass
                items.append({
                    "field": f,
                    "source": src,
                    "is_primary": src == route.primary,
                    "last_success_at": last_ok,
                    "last_error_at": health.get("last_error_at"),
                    "days_stale": days_stale,
                    "freshness": freshness,
                    "avg_latency_ms": float(health.get("avg_latency_ms", 0) or 0),
                    "error_rate_1h": float(health.get("error_rate_1h", 0) or 0),
                })

        return {
            "success": True,
            "data": {
                "market": m,
                "items": items,
                "timestamp": _now_iso(),
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("get_freshness failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"failed: {exc}")


# ---------------------------------------------------------------------------
# 源在线状态
# ---------------------------------------------------------------------------
@router.get("/online-status")
async def get_online_status(current_user: dict = Depends(require_admin)):
    """快速检测所有适配器的在线/离线状态。"""
    try:
        import time as _time
        from backend.services.engine.data_platform.base import InvalidFieldRequest

        reg = _get_registry()
        items: list[dict[str, Any]] = []

        for name in reg.list_sources():
            adapter = reg.get(name)
            status = "unknown"
            latency_ms = None
            error_msg = None

            # 轻量检测：尝试 fetch_meta 或直接标记
            t0 = _time.monotonic()
            try:
                # 用第一个 market 做 fetch_meta 检测
                if adapter.markets:
                    test_market = adapter.markets[0]
                    adapter.fetch_meta(test_market)
                status = "online"
                latency_ms = round((_time.monotonic() - t0) * 1000, 1)
            except InvalidFieldRequest:
                # 适配器不支持 fetch_meta（如 easyquotation 仅支持 realtime）
                status = "online" if adapter.fields else "unavailable"
                latency_ms = round((_time.monotonic() - t0) * 1000, 1)
            except Exception as exc:
                # 适配器不支持 fetch_meta（如 easyquotation 仅支持 realtime）
                # 检查它是否至少有可用字段
                status = "online" if adapter.fields else "unavailable"
                latency_ms = round((_time.monotonic() - t0) * 1000, 1)
            except Exception as exc:
                latency_ms = round((_time.monotonic() - t0) * 1000, 1)
                msg = str(exc).lower()
                if "not installed" in msg or "未安装" in msg or "未配置" in msg:
                    status = "unavailable"
                else:
                    status = "error"
                error_msg = str(exc)[:200]

            items.append({
                "name": name,
                "class": adapter.__class__.__name__,
                "markets": adapter.markets,
                "fields": sorted(adapter.fields),
                "status": status,
                "latency_ms": latency_ms,
                "error": error_msg,
                "checked_at": _now_iso(),
            })

        return {
            "success": True,
            "data": {
                "items": items,
                "total": len(items),
                "online": sum(1 for i in items if i["status"] == "online"),
                "offline": sum(1 for i in items if i["status"] in ("error", "unavailable")),
                "timestamp": _now_iso(),
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("get_online_status failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"failed: {exc}")
