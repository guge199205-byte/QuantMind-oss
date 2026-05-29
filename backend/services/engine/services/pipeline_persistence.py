from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text

from backend.shared.database_manager_v2 import get_session


class PipelinePersistence:
    """Pipeline run persistence backed by PostgreSQL."""

    async def ensure_tables(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS pipeline_runs (
              run_id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL DEFAULT 'default',
              status TEXT NOT NULL,
              stage TEXT NOT NULL,
              error_message TEXT,
              created_at TIMESTAMPTZ NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL,
              request_json JSONB,
              result_json JSONB
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_pipeline_runs_tenant_created
              ON pipeline_runs(tenant_id, created_at DESC);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status
              ON pipeline_runs(status);
            """,
        ]
        async with get_session() as session:
            for stmt in statements:
                await session.execute(text(stmt))

    async def create_run(
        self,
        *,
        run_id: str,
        user_id: str,
        tenant_id: str,
        status: str,
        stage: str,
        created_at: datetime,
        request_payload: dict[str, Any],
    ) -> None:
        async with get_session() as session:
            await session.execute(
                text("""
                    INSERT INTO pipeline_runs (
                      run_id, user_id, tenant_id, status, stage,
                      error_message, created_at, updated_at, request_json, result_json
                    ) VALUES (
                      :run_id, :user_id, :tenant_id, :status, :stage,
                      NULL, :created_at, :updated_at,
                      CAST(:request_json AS jsonb), NULL
                    )
                    ON CONFLICT(run_id) DO UPDATE SET
                      user_id = EXCLUDED.user_id,
                      tenant_id = EXCLUDED.tenant_id,
                      status = EXCLUDED.status,
                      stage = EXCLUDED.stage,
                      error_message = EXCLUDED.error_message,
                      updated_at = EXCLUDED.updated_at,
                      request_json = EXCLUDED.request_json
                    """),
                {
                    "run_id": run_id,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "status": status,
                    "stage": stage,
                    "created_at": created_at,
                    "updated_at": created_at,
                    "request_json": json.dumps(request_payload, ensure_ascii=False),
                },
            )

    async def update_run(
        self,
        *,
        run_id: str,
        status: str,
        stage: str,
        updated_at: datetime,
        error_message: str | None = None,
        result_payload: dict[str, Any] | None = None,
    ) -> None:
        async with get_session() as session:
            await session.execute(
                text("""
                    UPDATE pipeline_runs
                    SET status = :status,
                        stage = :stage,
                        error_message = :error_message,
                        updated_at = :updated_at,
                        result_json = CASE
                          WHEN :result_json IS NULL THEN result_json
                          ELSE CAST(:result_json AS jsonb)
                        END
                    WHERE run_id = :run_id
                    """),
                {
                    "run_id": run_id,
                    "status": status,
                    "stage": stage,
                    "error_message": error_message,
                    "updated_at": updated_at,
                    "result_json": (
                        json.dumps(result_payload, ensure_ascii=False) if result_payload is not None else None
                    ),
                },
            )

    async def get_run(self, run_id: str, *, user_id: str, tenant_id: str) -> dict[str, Any] | None:
        async with get_session(read_only=True) as session:
            row = await session.execute(
                text("""
                    SELECT run_id, user_id, tenant_id, status, stage, error_message,
                           created_at, updated_at, request_json, result_json
                    FROM pipeline_runs
                    WHERE run_id = :run_id
                      AND user_id = :user_id
                      AND tenant_id = :tenant_id
                    """),
                {"run_id": run_id, "user_id": user_id, "tenant_id": tenant_id},
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

    async def get_run_by_id(self, run_id: str) -> dict[str, Any] | None:
        """按 run_id 查询（用于异步 worker 恢复执行上下文）。"""
        async with get_session(read_only=True) as session:
            row = await session.execute(
                text("""
                    SELECT run_id, user_id, tenant_id, status, stage, error_message,
                           created_at, updated_at, request_json, result_json
                    FROM pipeline_runs
                    WHERE run_id = :run_id
                    """),
                {"run_id": run_id},
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

    async def cleanup_old_runs(self, *, user_id: str, tenant_id: str, keep_days: int = 30) -> int:
        async with get_session() as session:
            deleted = await session.execute(
                text("""
                    DELETE FROM pipeline_runs
                    WHERE user_id = :user_id
                      AND tenant_id = :tenant_id
                      AND created_at < (NOW() - make_interval(days => :keep_days))
                    """),
                {
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "keep_days": int(keep_days),
                },
            )
            return int(deleted.rowcount or 0)
