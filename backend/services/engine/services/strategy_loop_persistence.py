from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from backend.shared.database_manager_v2 import get_session


class StrategyLoopPersistence:
    """strategy-backtest-loop 任务持久化。"""

    async def ensure_tables(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS strategy_loop_tasks (
              task_id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL DEFAULT 'default',
              status TEXT NOT NULL,
              error_message TEXT,
              created_at TIMESTAMPTZ NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL,
              request_json JSONB,
              result_json JSONB
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_strategy_loop_tasks_user_tenant_created
              ON strategy_loop_tasks(user_id, tenant_id, created_at DESC);
            """,
        ]
        async with get_session() as session:
            for stmt in statements:
                await session.execute(text(stmt))

    async def create_task(
        self,
        *,
        task_id: str,
        user_id: str,
        tenant_id: str,
        status: str,
        created_at: datetime,
        request_payload: dict[str, Any],
    ) -> None:
        async with get_session() as session:
            await session.execute(
                text("""
                    INSERT INTO strategy_loop_tasks (
                      task_id, user_id, tenant_id, status, error_message,
                      created_at, updated_at, request_json, result_json
                    ) VALUES (
                      :task_id, :user_id, :tenant_id, :status, NULL,
                      :created_at, :updated_at, CAST(:request_json AS jsonb), NULL
                    )
                    ON CONFLICT(task_id) DO UPDATE SET
                      user_id = EXCLUDED.user_id,
                      tenant_id = EXCLUDED.tenant_id,
                      status = EXCLUDED.status,
                      updated_at = EXCLUDED.updated_at,
                      request_json = EXCLUDED.request_json
                    """),
                {
                    "task_id": task_id,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "status": status,
                    "created_at": created_at,
                    "updated_at": created_at,
                    "request_json": json.dumps(request_payload, ensure_ascii=False),
                },
            )

    async def update_task(
        self,
        *,
        task_id: str,
        status: str,
        updated_at: datetime,
        error_message: str | None = None,
        result_payload: dict[str, Any] | None = None,
    ) -> None:
        async with get_session() as session:
            await session.execute(
                text("""
                    UPDATE strategy_loop_tasks
                    SET status = :status,
                        error_message = :error_message,
                        updated_at = :updated_at,
                        result_json = CASE
                          WHEN :result_json IS NULL THEN result_json
                          ELSE CAST(:result_json AS jsonb)
                        END
                    WHERE task_id = :task_id
                    """),
                {
                    "task_id": task_id,
                    "status": status,
                    "error_message": error_message,
                    "updated_at": updated_at,
                    "result_json": (
                        json.dumps(result_payload, ensure_ascii=False) if result_payload is not None else None
                    ),
                },
            )

    async def get_task(self, task_id: str, *, user_id: str, tenant_id: str) -> dict[str, Any] | None:
        async with get_session(read_only=True) as session:
            row = await session.execute(
                text("""
                    SELECT task_id, user_id, tenant_id, status, error_message,
                           created_at, updated_at, request_json, result_json
                    FROM strategy_loop_tasks
                    WHERE task_id = :task_id
                      AND user_id = :user_id
                      AND tenant_id = :tenant_id
                    """),
                {"task_id": task_id, "user_id": user_id, "tenant_id": tenant_id},
            )
            mapping = row.mappings().first()
        if mapping is None:
            return None
        result = dict(mapping)
        if isinstance(result.get("request_json"), str):
            result["request_json"] = json.loads(result["request_json"])
        if isinstance(result.get("result_json"), str):
            result["result_json"] = json.loads(result["result_json"])
        return result

    async def list_tasks(self, *, user_id: str, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        async with get_session(read_only=True) as session:
            rows = await session.execute(
                text("""
                    SELECT task_id, status, error_message, created_at, updated_at, result_json
                    FROM strategy_loop_tasks
                    WHERE user_id = :user_id
                      AND tenant_id = :tenant_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """),
                {"user_id": user_id, "tenant_id": tenant_id, "limit": int(limit)},
            )
            mappings = rows.mappings().all()
        result: list[dict[str, Any]] = []
        for row in mappings:
            item = dict(row)
            if isinstance(item.get("result_json"), str):
                item["result_json"] = json.loads(item["result_json"])
            result.append(item)
        return result

    async def cleanup_old_tasks(self, *, keep_days: int = 30) -> int:
        """清理旧的任务记录。"""
        async with get_session() as session:
            deleted = await session.execute(
                text("""
                    DELETE FROM strategy_loop_tasks
                    WHERE created_at < (NOW() - make_interval(days => :keep_days))
                    """),
                {"keep_days": int(keep_days)},
            )
            return int(deleted.rowcount or 0)
