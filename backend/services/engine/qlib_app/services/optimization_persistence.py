"""参数优化历史持久化（PostgreSQL）"""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from backend.shared.database_manager_v2 import get_session
from backend.shared.utils import normalize_user_id

logger = logging.getLogger(__name__)


class OptimizationPersistence:
    """参数优化历史持久化"""

    HISTORY_RETENTION_LIMIT = 20

    async def ensure_tables(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS qlib_optimization_runs (
              optimization_id TEXT PRIMARY KEY,
              task_id TEXT,
              mode TEXT NOT NULL,
              user_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL DEFAULT 'default',
              status TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL,
              completed_at TIMESTAMPTZ,
              base_request_json JSONB,
              config_snapshot_json JSONB,
              optimization_target TEXT,
              param_ranges_json JSONB,
              total_tasks INT NOT NULL DEFAULT 0,
              completed_count INT NOT NULL DEFAULT 0,
              failed_count INT NOT NULL DEFAULT 0,
              current_params_json JSONB,
              best_params_json JSONB,
              best_metric_value DOUBLE PRECISION,
              result_summary_json JSONB,
              all_results_json JSONB,
              error_message TEXT
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_qlib_optimization_runs_user_created
              ON qlib_optimization_runs(user_id, created_at DESC);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_qlib_optimization_runs_tenant_created
              ON qlib_optimization_runs(tenant_id, created_at DESC);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_qlib_optimization_runs_status
              ON qlib_optimization_runs(status);
            """,
        ]
        async with get_session() as session:
            for statement in statements:
                await session.execute(text(statement))

    async def create_run(
        self,
        *,
        optimization_id: str,
        task_id: str,
        mode: str,
        user_id: str,
        tenant_id: str,
        status: str,
        base_request: dict[str, Any] | None,
        config_snapshot: dict[str, Any] | None,
        optimization_target: str,
        param_ranges: list[dict[str, Any]],
        total_tasks: int,
        completed_count: int = 0,
        failed_count: int = 0,
        current_params: dict[str, Any] | None = None,
        best_params: dict[str, Any] | None = None,
        best_metric_value: float | None = None,
        result_summary: dict[str, Any] | None = None,
        all_results: list[dict[str, Any]] | None = None,
        error_message: str | None = None,
    ) -> None:
        user_id = normalize_user_id(user_id)
        now = datetime.now()
        async with get_session() as session:
            await session.execute(
                text("""
                    INSERT INTO qlib_optimization_runs (
                      optimization_id, task_id, mode, user_id, tenant_id, status,
                      created_at, updated_at, completed_at,
                      base_request_json, config_snapshot_json, optimization_target,
                      param_ranges_json, total_tasks, completed_count, failed_count,
                      current_params_json, best_params_json, best_metric_value,
                      result_summary_json, all_results_json, error_message
                    ) VALUES (
                      :optimization_id, :task_id, :mode, :user_id, :tenant_id, :status,
                      :created_at, :updated_at, :completed_at,
                      CAST(:base_request_json AS jsonb), CAST(:config_snapshot_json AS jsonb), :optimization_target,
                      CAST(:param_ranges_json AS jsonb), :total_tasks, :completed_count, :failed_count,
                      CAST(:current_params_json AS jsonb), CAST(:best_params_json AS jsonb), :best_metric_value,
                      CAST(:result_summary_json AS jsonb), CAST(:all_results_json AS jsonb), :error_message
                    )
                    ON CONFLICT (optimization_id) DO UPDATE SET
                      task_id = EXCLUDED.task_id,
                      mode = EXCLUDED.mode,
                      user_id = EXCLUDED.user_id,
                      tenant_id = EXCLUDED.tenant_id,
                      status = EXCLUDED.status,
                      updated_at = EXCLUDED.updated_at,
                      completed_at = EXCLUDED.completed_at,
                      base_request_json = EXCLUDED.base_request_json,
                      config_snapshot_json = EXCLUDED.config_snapshot_json,
                      optimization_target = EXCLUDED.optimization_target,
                      param_ranges_json = EXCLUDED.param_ranges_json,
                      total_tasks = EXCLUDED.total_tasks,
                      completed_count = EXCLUDED.completed_count,
                      failed_count = EXCLUDED.failed_count,
                      current_params_json = EXCLUDED.current_params_json,
                      best_params_json = EXCLUDED.best_params_json,
                      best_metric_value = EXCLUDED.best_metric_value,
                      result_summary_json = EXCLUDED.result_summary_json,
                      all_results_json = EXCLUDED.all_results_json,
                      error_message = EXCLUDED.error_message
                    """),
                {
                    "optimization_id": optimization_id,
                    "task_id": task_id,
                    "mode": mode,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "status": status,
                    "created_at": now,
                    "updated_at": now,
                    "completed_at": now if status in ("completed", "failed", "cancelled") else None,
                    "base_request_json": json.dumps(base_request or {}, ensure_ascii=False),
                    "config_snapshot_json": json.dumps(config_snapshot or {}, ensure_ascii=False),
                    "optimization_target": optimization_target,
                    "param_ranges_json": json.dumps(param_ranges or [], ensure_ascii=False),
                    "total_tasks": total_tasks,
                    "completed_count": completed_count,
                    "failed_count": failed_count,
                    "current_params_json": (
                        json.dumps(current_params, ensure_ascii=False) if current_params is not None else None
                    ),
                    "best_params_json": (
                        json.dumps(best_params, ensure_ascii=False) if best_params is not None else None
                    ),
                    "best_metric_value": best_metric_value,
                    "result_summary_json": json.dumps(result_summary or {}, ensure_ascii=False),
                    "all_results_json": json.dumps(all_results or [], ensure_ascii=False),
                    "error_message": error_message,
                },
            )
            await self._prune_user_history(session, user_id, tenant_id)

    async def update_run(
        self,
        optimization_id: str,
        *,
        status: str | None = None,
        completed_count: int | None = None,
        failed_count: int | None = None,
        current_params: dict[str, Any] | None = None,
        best_params: dict[str, Any] | None = None,
        best_metric_value: float | None = None,
        result_summary: dict[str, Any] | None = None,
        all_results: list[dict[str, Any]] | None = None,
        error_message: str | None = None,
    ) -> None:
        fields = ["updated_at = :updated_at"]
        params: dict[str, Any] = {
            "optimization_id": optimization_id,
            "updated_at": datetime.now(),
        }
        if status is not None:
            fields.append("status = :status")
            params["status"] = status
            if status in ("completed", "failed", "cancelled"):
                fields.append("completed_at = :completed_at")
                params["completed_at"] = datetime.now()
        if completed_count is not None:
            fields.append("completed_count = :completed_count")
            params["completed_count"] = completed_count
        if failed_count is not None:
            fields.append("failed_count = :failed_count")
            params["failed_count"] = failed_count
        if current_params is not None:
            fields.append("current_params_json = CAST(:current_params_json AS jsonb)")
            params["current_params_json"] = json.dumps(current_params, ensure_ascii=False)
        if best_params is not None:
            fields.append("best_params_json = CAST(:best_params_json AS jsonb)")
            params["best_params_json"] = json.dumps(best_params, ensure_ascii=False)
        if best_metric_value is not None:
            fields.append("best_metric_value = :best_metric_value")
            params["best_metric_value"] = best_metric_value
        if result_summary is not None:
            fields.append("result_summary_json = CAST(:result_summary_json AS jsonb)")
            params["result_summary_json"] = json.dumps(result_summary, ensure_ascii=False)
        if all_results is not None:
            fields.append("all_results_json = CAST(:all_results_json AS jsonb)")
            params["all_results_json"] = json.dumps(all_results, ensure_ascii=False)
        if error_message is not None:
            fields.append("error_message = :error_message")
            params["error_message"] = error_message

        async with get_session() as session:
            await session.execute(
                text(f"""
                    UPDATE qlib_optimization_runs
                    SET {", ".join(fields)}
                    WHERE optimization_id = :optimization_id
                    """),
                params,
            )

    async def list_history(
        self,
        user_id: str,
        *,
        tenant_id: str | None = None,
        limit: int = HISTORY_RETENTION_LIMIT,
    ) -> list[dict[str, Any]]:
        user_id = normalize_user_id(user_id)
        params: dict[str, Any] = {"user_id": user_id, "limit": max(1, int(limit))}
        tenant_sql = ""
        if tenant_id:
            tenant_sql = " AND tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id

        async with get_session(read_only=True) as session:
            rows = await session.execute(
                text("""
                    SELECT optimization_id, task_id, mode, user_id, tenant_id, status,
                           created_at, updated_at, completed_at, optimization_target,
                           total_tasks, completed_count, failed_count,
                           current_params_json, best_params_json, best_metric_value,
                           config_snapshot_json, error_message
                    FROM qlib_optimization_runs
                    WHERE user_id = :user_id
                    """ + tenant_sql + " ORDER BY created_at DESC LIMIT :limit"),
                params,
            )
            data = rows.mappings().all()
        return [self._map_row(row, include_all_results=False) for row in data]

    async def count_by_statuses(self, statuses: list[str]) -> int:
        normalized = [str(status).strip().lower() for status in statuses if str(status).strip()]
        if not normalized:
            return 0
        async with get_session(read_only=True) as session:
            row = await session.execute(
                text("""
                    SELECT COUNT(*) AS count
                    FROM qlib_optimization_runs
                    WHERE LOWER(status) = ANY(:statuses)
                    """),
                {"statuses": normalized},
            )
            data = row.mappings().first()
        return int(data.get("count") or 0) if data else 0

    async def get_detail(
        self,
        optimization_id: str,
        *,
        user_id: str,
        tenant_id: str | None = None,
    ) -> dict[str, Any] | None:
        user_id = normalize_user_id(user_id)
        params: dict[str, Any] = {
            "optimization_id": optimization_id,
            "user_id": user_id,
        }
        tenant_sql = ""
        if tenant_id:
            tenant_sql = " AND tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id

        async with get_session(read_only=True) as session:
            row = await session.execute(
                text("""
                    SELECT *
                    FROM qlib_optimization_runs
                    WHERE optimization_id = :optimization_id
                      AND user_id = :user_id
                    """ + tenant_sql),
                params,
            )
            data = row.mappings().first()
        if not data:
            return None
        return self._map_row(data, include_all_results=True)

    async def get_status(self, optimization_id: str) -> str | None:
        async with get_session(read_only=True) as session:
            row = await session.execute(
                text("""
                    SELECT status
                    FROM qlib_optimization_runs
                    WHERE optimization_id = :optimization_id
                    LIMIT 1
                    """),
                {"optimization_id": optimization_id},
            )
            data = row.mappings().first()
        if not data:
            return None
        return str(data.get("status") or "").strip().lower() or None

    async def get_optimization_id_by_task_id(self, task_id: str) -> str | None:
        async with get_session(read_only=True) as session:
            row = await session.execute(
                text("""
                    SELECT optimization_id
                    FROM qlib_optimization_runs
                    WHERE task_id = :task_id
                    ORDER BY created_at DESC
                    LIMIT 1
                    """),
                {"task_id": task_id},
            )
            data = row.mappings().first()
        if not data:
            return None
        optimization_id = data.get("optimization_id")
        return str(optimization_id) if optimization_id else None

    def _map_row(self, row: dict[str, Any], *, include_all_results: bool) -> dict[str, Any]:
        payload = {
            "optimization_id": row["optimization_id"],
            "task_id": row.get("task_id"),
            "mode": row.get("mode") or "grid_search",
            "user_id": row.get("user_id"),
            "tenant_id": row.get("tenant_id") or "default",
            "status": row.get("status") or "running",
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "completed_at": row.get("completed_at"),
            "optimization_target": row.get("optimization_target"),
            "total_tasks": row.get("total_tasks") or 0,
            "completed_count": row.get("completed_count") or 0,
            "failed_count": row.get("failed_count") or 0,
            "current_params": row.get("current_params_json") or None,
            "best_params": row.get("best_params_json") or None,
            "best_metric_value": row.get("best_metric_value"),
            "config_snapshot": row.get("config_snapshot_json") or {},
            "error_message": row.get("error_message"),
            "can_apply": (row.get("status") == "completed"),
        }
        if include_all_results:
            payload.update(
                {
                    "base_request": row.get("base_request_json") or {},
                    "param_ranges": row.get("param_ranges_json") or [],
                    "result_summary": row.get("result_summary_json") or {},
                    "all_results": row.get("all_results_json") or [],
                }
            )
        return payload

    async def _prune_user_history(self, session, user_id: str, tenant_id: str) -> None:
        rows = await session.execute(
            text("""
                SELECT optimization_id
                FROM qlib_optimization_runs
                WHERE user_id = :user_id AND tenant_id = :tenant_id
                ORDER BY created_at DESC
                OFFSET :offset
                """),
            {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "offset": self.HISTORY_RETENTION_LIMIT,
            },
        )
        expired_ids = [row[0] for row in rows.fetchall()]
        if not expired_ids:
            return
        await session.execute(
            text("DELETE FROM qlib_optimization_runs WHERE optimization_id = ANY(:ids)"),
            {"ids": expired_ids},
        )

    async def clear_history(self, user_id: str, tenant_id: str) -> bool:
        """一键清除用户的所有优化历史记录并清理相关物理目录"""
        user_id = normalize_user_id(user_id)
        async with get_session() as session:
            # 1. 从数据库中删除所有记录
            result = await session.execute(
                text("""
                    DELETE FROM qlib_optimization_runs
                    WHERE user_id = :user_id AND tenant_id = :tenant_id
                    """),
                {"user_id": user_id, "tenant_id": tenant_id},
            )

            # 2. 清理用户物理结果目录 (如有)
            # 虽然优化子任务默认不存盘，但为了彻底响应用户需求并保持环境整洁，
            # 我们清理该租户下该用户的所有回测/优化相关物理轨迹。
            try:
                from backend.services.engine.qlib_app.services.backtest_persistence import (
                    BacktestPersistence,
                )

                bp = BacktestPersistence()
                # 构造路径: data/backtest_results/[tenant]/[user]
                user_root = bp._local_result_root / bp._sanitize_segment(tenant_id) / bp._sanitize_segment(user_id)
                if user_root.exists() and user_root.is_dir():
                    shutil.rmtree(user_root)
                    logger.info(f"Cleared physical history directory: {user_root}")
            except Exception as e:
                logger.warning(f"Failed to clear physical history directory: {e}")

            return result.rowcount > 0
