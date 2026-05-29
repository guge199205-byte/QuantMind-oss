from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


from sqlalchemy import text

from backend.shared.database_manager_v2 import get_session


class ManualExecutionPersistence:
    """实盘页手动执行任务持久化。"""

    async def ensure_tables(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS trade_manual_execution_tasks (
              task_id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL DEFAULT 'default',
              user_id TEXT NOT NULL,
              strategy_id TEXT NOT NULL,
              strategy_name TEXT NOT NULL,
              run_id TEXT NOT NULL,
              model_id TEXT NOT NULL,
              prediction_trade_date DATE NOT NULL,
              trading_mode TEXT NOT NULL,
              status TEXT NOT NULL,
              stage TEXT NOT NULL DEFAULT 'queued',
              error_stage TEXT,
              error_message TEXT,
              signal_count INTEGER NOT NULL DEFAULT 0,
              order_count INTEGER NOT NULL DEFAULT 0,
              success_count INTEGER NOT NULL DEFAULT 0,
              failed_count INTEGER NOT NULL DEFAULT 0,
              request_json JSONB,
              result_json JSONB,
              created_at TIMESTAMPTZ NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL
            );
            """,
            """
            ALTER TABLE trade_manual_execution_tasks
            ADD COLUMN IF NOT EXISTS progress INTEGER NOT NULL DEFAULT 0;
            """,
            """
            ALTER TABLE trade_manual_execution_tasks
            ADD COLUMN IF NOT EXISTS task_type TEXT NOT NULL DEFAULT 'manual';
            """,
            """
            ALTER TABLE trade_manual_execution_tasks
            ADD COLUMN IF NOT EXISTS task_source TEXT NOT NULL DEFAULT 'manual_page';
            """,
            """
            ALTER TABLE trade_manual_execution_tasks
            ADD COLUMN IF NOT EXISTS trigger_mode TEXT NOT NULL DEFAULT 'manual';
            """,
            """
            ALTER TABLE trade_manual_execution_tasks
            ADD COLUMN IF NOT EXISTS trigger_context_json JSONB;
            """,
            """
            ALTER TABLE trade_manual_execution_tasks
            ADD COLUMN IF NOT EXISTS strategy_snapshot_json JSONB;
            """,
            """
            ALTER TABLE trade_manual_execution_tasks
            ADD COLUMN IF NOT EXISTS parent_runtime_id TEXT;
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_trade_manual_execution_tasks_owner_created
              ON trade_manual_execution_tasks(tenant_id, user_id, created_at DESC);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_trade_manual_execution_tasks_status_created
              ON trade_manual_execution_tasks(status, created_at DESC);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_trade_manual_execution_tasks_type_created
              ON trade_manual_execution_tasks(task_type, created_at DESC);
            """,
        ]
        async with get_session() as session:
            for stmt in statements:
                await session.execute(text(stmt))

    @staticmethod
    def _parse_json_field(value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

    @staticmethod
    def _row_to_task(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        for key in ("created_at", "updated_at"):
            if result.get(key) is not None:
                result[key] = result[key].isoformat()
        if result.get("prediction_trade_date") is not None:
            result["prediction_trade_date"] = str(result["prediction_trade_date"])
        result["request_json"] = ManualExecutionPersistence._parse_json_field(result.get("request_json"))
        result["result_json"] = ManualExecutionPersistence._parse_json_field(result.get("result_json"))
        result["trigger_context_json"] = ManualExecutionPersistence._parse_json_field(
            result.get("trigger_context_json")
        )
        result["strategy_snapshot_json"] = ManualExecutionPersistence._parse_json_field(
            result.get("strategy_snapshot_json")
        )
        return result

    async def create_task(
        self,
        *,
        task_id: str,
        tenant_id: str,
        user_id: str,
        strategy_id: str,
        strategy_name: str,
        run_id: str,
        model_id: str,
        prediction_trade_date,
        trading_mode: str,
        request_payload: dict[str, Any],
        created_at: datetime,
        task_type: str = "manual",
        task_source: str = "manual_page",
        trigger_mode: str = "manual",
        trigger_context: dict[str, Any] | None = None,
        strategy_snapshot: dict[str, Any] | None = None,
        parent_runtime_id: str | None = None,
    ) -> None:
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO trade_manual_execution_tasks (
                      task_id, tenant_id, user_id, strategy_id, strategy_name,
                      run_id, model_id, prediction_trade_date, trading_mode,
                      task_type, task_source, trigger_mode, trigger_context_json,
                      strategy_snapshot_json, parent_runtime_id,
                      status, stage, error_stage, error_message,
                      signal_count, order_count, success_count, failed_count,
                      request_json, result_json, created_at, updated_at
                    ) VALUES (
                      :task_id, :tenant_id, :user_id, :strategy_id, :strategy_name,
                      :run_id, :model_id, :prediction_trade_date, :trading_mode,
                      :task_type, :task_source, :trigger_mode,
                      CAST(:trigger_context_json AS jsonb),
                      CAST(:strategy_snapshot_json AS jsonb),
                      :parent_runtime_id,
                      :status, :stage, NULL, NULL,
                      0, 0, 0, 0,
                      CAST(:request_json AS jsonb), NULL, :created_at, :created_at
                    )
                    ON CONFLICT (task_id) DO UPDATE SET
                      tenant_id = EXCLUDED.tenant_id,
                      user_id = EXCLUDED.user_id,
                      strategy_id = EXCLUDED.strategy_id,
                      strategy_name = EXCLUDED.strategy_name,
                      run_id = EXCLUDED.run_id,
                      model_id = EXCLUDED.model_id,
                      prediction_trade_date = EXCLUDED.prediction_trade_date,
                      trading_mode = EXCLUDED.trading_mode,
                      task_type = EXCLUDED.task_type,
                      task_source = EXCLUDED.task_source,
                      trigger_mode = EXCLUDED.trigger_mode,
                      trigger_context_json = EXCLUDED.trigger_context_json,
                      strategy_snapshot_json = EXCLUDED.strategy_snapshot_json,
                      parent_runtime_id = EXCLUDED.parent_runtime_id,
                      status = EXCLUDED.status,
                      stage = EXCLUDED.stage,
                      updated_at = EXCLUDED.updated_at,
                      request_json = EXCLUDED.request_json
                    """
                ),
                {
                    "task_id": task_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "strategy_id": strategy_id,
                    "strategy_name": strategy_name,
                    "run_id": run_id,
                    "model_id": model_id,
                    "prediction_trade_date": prediction_trade_date,
                    "trading_mode": trading_mode,
                    "task_type": task_type,
                    "task_source": task_source,
                    "trigger_mode": trigger_mode,
                    "trigger_context_json": (
                        json.dumps(trigger_context, ensure_ascii=False)
                        if trigger_context is not None
                        else None
                    ),
                    "strategy_snapshot_json": (
                        json.dumps(strategy_snapshot, ensure_ascii=False)
                        if strategy_snapshot is not None
                        else None
                    ),
                    "parent_runtime_id": parent_runtime_id,
                    "status": "queued",
                    "stage": "queued",
                    "request_json": json.dumps(request_payload, ensure_ascii=False),
                    "created_at": created_at,
                },
            )

    async def claim_next_queued_task(self) -> dict[str, Any] | None:
        async with get_session() as session:
            row = (
                await session.execute(
                    text(
                        """
                        WITH picked AS (
                          SELECT task_id
                          FROM trade_manual_execution_tasks
                          WHERE status = 'queued'
                          ORDER BY created_at ASC
                          FOR UPDATE SKIP LOCKED
                          LIMIT 1
                        )
                        UPDATE trade_manual_execution_tasks t
                        SET status = 'validating',
                            stage = 'validating',
                            updated_at = NOW()
                        FROM picked
                        WHERE t.task_id = picked.task_id
                        RETURNING t.*
                        """
                    )
                )
            ).mappings().first()
        return self._row_to_task(dict(row)) if row else None

    async def update_task(
        self,
        *,
        task_id: str,
        status: str,
        stage: str | None = None,
        updated_at: datetime | None = None,
        error_stage: str | None = None,
        error_message: str | None = None,
        signal_count: int | None = None,
        order_count: int | None = None,
        success_count: int | None = None,
        failed_count: int | None = None,
        progress: int | None = None,
        result_payload: dict[str, Any] | None = None,
    ) -> None:
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE trade_manual_execution_tasks
                    SET status = :status,
                        stage = COALESCE(:stage, stage),
                        error_stage = :error_stage,
                        error_message = :error_message,
                        signal_count = COALESCE(:signal_count, signal_count),
                        order_count = COALESCE(:order_count, order_count),
                        success_count = COALESCE(:success_count, success_count),
                        failed_count = COALESCE(:failed_count, failed_count),
                        progress = COALESCE(:progress, progress),
                        updated_at = :updated_at,
                        result_json = CASE
                          WHEN CAST(:result_json AS TEXT) IS NULL THEN result_json
                          ELSE CAST(:result_json AS jsonb)
                        END
                    WHERE task_id = :task_id
                    """
                ),
                {
                    "task_id": task_id,
                    "status": status,
                    "stage": stage,
                    "error_stage": error_stage,
                    "error_message": error_message,
                    "signal_count": signal_count,
                    "order_count": order_count,
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "progress": progress,
                    "updated_at": updated_at or datetime.now(timezone.utc),
                    "result_json": json.dumps(result_payload, ensure_ascii=False) if result_payload is not None else None,
                },
            )

    async def get_task(self, task_id: str, *, user_id: str, tenant_id: str) -> dict[str, Any] | None:
        async with get_session(read_only=True) as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT *
                        FROM trade_manual_execution_tasks
                        WHERE task_id = :task_id
                          AND user_id = :user_id
                          AND tenant_id = :tenant_id
                        LIMIT 1
                        """
                    ),
                    {"task_id": task_id, "user_id": user_id, "tenant_id": tenant_id},
                )
            ).mappings().first()
        return self._row_to_task(dict(row)) if row else None

    async def get_task_any(self, task_id: str) -> dict[str, Any] | None:
        async with get_session(read_only=True) as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT *
                        FROM trade_manual_execution_tasks
                        WHERE task_id = :task_id
                        LIMIT 1
                        """
                    ),
                    {"task_id": task_id},
                )
            ).mappings().first()
        return self._row_to_task(dict(row)) if row else None

    async def list_tasks(
        self,
        *,
        user_id: str,
        tenant_id: str,
        limit: int = 20,
        task_type: str | None = None,
        task_source: str | None = None,
        parent_runtime_id: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["user_id = :user_id", "tenant_id = :tenant_id"]
        params: dict[str, Any] = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "limit": int(limit),
        }
        normalized_task_type = str(task_type or "").strip().lower()
        if normalized_task_type:
            conditions.append("task_type = :task_type")
            params["task_type"] = normalized_task_type
        normalized_task_source = str(task_source or "").strip().lower()
        if normalized_task_source:
            conditions.append("task_source = :task_source")
            params["task_source"] = normalized_task_source
        normalized_parent_runtime_id = str(parent_runtime_id or "").strip()
        if normalized_parent_runtime_id:
            conditions.append("parent_runtime_id = :parent_runtime_id")
            params["parent_runtime_id"] = normalized_parent_runtime_id
        async with get_session(read_only=True) as session:
            rows = (
                await session.execute(
                    text(
                        f"""
                        SELECT *
                        FROM trade_manual_execution_tasks
                        WHERE {" AND ".join(conditions)}
                        ORDER BY created_at DESC
                        LIMIT :limit
                        """
                    ),
                    params,
                )
            ).mappings().all()
        return [self._row_to_task(dict(row)) for row in rows]

    async def clear_tasks(
        self,
        *,
        user_id: str,
        tenant_id: str,
    ) -> int:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    DELETE FROM trade_manual_execution_tasks
                    WHERE user_id = :user_id
                      AND tenant_id = :tenant_id
                    """
                ),
                {"user_id": user_id, "tenant_id": tenant_id},
            )
            await session.commit()
            return result.rowcount


manual_execution_persistence = ManualExecutionPersistence()
