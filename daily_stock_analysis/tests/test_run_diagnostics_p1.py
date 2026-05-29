# -*- coding: utf-8 -*-
"""Regression tests for #1391 Phase 1 run diagnostics."""

from __future__ import annotations

import os
import sys
import unittest
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.base import BaseFetcher, DataFetcherManager
from src.services.run_diagnostics import (
    activate_run_diagnostic_context,
    current_diagnostic_snapshot,
    record_provider_run,
    reset_run_diagnostic_context,
)
from src.services.task_queue import AnalysisTaskQueue, TaskInfo, TaskStatus


class _FailingDailyFetcher(BaseFetcher):
    name = "FailingDailyFetcher"
    priority = 0

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        raise NotImplementedError

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        raise NotImplementedError

    def get_daily_data(self, stock_code, start_date=None, end_date=None, days=30):
        raise RuntimeError("token=secret-token")


class _SuccessfulDailyFetcher(BaseFetcher):
    name = "SuccessfulDailyFetcher"
    priority = 1

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        raise NotImplementedError

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        raise NotImplementedError

    def get_daily_data(self, stock_code, start_date=None, end_date=None, days=30):
        return pd.DataFrame(
            [
                {
                    "date": "2026-05-22",
                    "open": 1,
                    "high": 2,
                    "low": 1,
                    "close": 2,
                    "volume": 100,
                    "amount": 200,
                    "pct_chg": 1,
                }
            ]
        )


class _Quote:
    name = "贵州茅台"
    price = 100
    change_pct = 1.2
    volume_ratio = 1.1
    turnover_rate = 0.5
    pe_ratio = 10
    pb_ratio = 2
    total_mv = 1000
    circ_mv = 800
    amplitude = 2

    def has_basic_data(self) -> bool:
        return True


class _EfinanceRealtimeFetcher(BaseFetcher):
    name = "EfinanceFetcher"
    priority = 0

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        raise NotImplementedError

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        raise NotImplementedError

    def get_realtime_quote(self, stock_code):
        return _Quote()


class _SyncExecutor:
    def submit(self, fn, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:  # pragma: no cover - exercised by queue behavior
            future.set_exception(exc)
        return future

    def shutdown(self, wait=True):
        return None


class RunDiagnosticsP1TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._original_queue = AnalysisTaskQueue._instance
        AnalysisTaskQueue._instance = None

    def tearDown(self) -> None:
        queue = AnalysisTaskQueue._instance
        if queue is not None and queue is not self._original_queue:
            executor = getattr(queue, "_executor", None)
            if executor is not None and hasattr(executor, "shutdown"):
                executor.shutdown(wait=False)
        AnalysisTaskQueue._instance = self._original_queue

    def test_task_info_exposes_trace_id_for_sse_and_status_payloads(self) -> None:
        task = TaskInfo(task_id="task-1", stock_code="600519")

        self.assertEqual(task.to_dict()["trace_id"], "task-1")
        self.assertEqual(task.copy().trace_id, "task-1")

    def test_background_task_reuses_task_id_as_trace_id(self) -> None:
        queue = AnalysisTaskQueue(max_workers=1)
        queue._executor = _SyncExecutor()

        task = queue.submit_background_task(
            lambda: {"ok": True},
            stock_code="market_review",
            task_id="market-task-1",
        )
        stored = queue.get_task(task.task_id)

        self.assertIsNotNone(stored)
        self.assertEqual(stored.trace_id, "market-task-1")
        self.assertEqual(stored.status, TaskStatus.COMPLETED)

    def test_daily_data_provider_runs_record_failure_then_success(self) -> None:
        manager = DataFetcherManager(
            fetchers=[_FailingDailyFetcher(), _SuccessfulDailyFetcher()]
        )
        token = activate_run_diagnostic_context(
            trace_id="trace-daily",
            query_id="query-daily",
            stock_code="600519",
            trigger_source="api",
        )
        try:
            df, source = manager.get_daily_data("600519")
            snapshot = current_diagnostic_snapshot()
        finally:
            reset_run_diagnostic_context(token)

        self.assertFalse(df.empty)
        self.assertEqual(source, "SuccessfulDailyFetcher")
        runs = snapshot["provider_runs"]
        self.assertEqual([run["provider"] for run in runs], ["FailingDailyFetcher", "SuccessfulDailyFetcher"])
        self.assertFalse(runs[0]["success"])
        self.assertEqual(runs[0]["fallback_to"], "SuccessfulDailyFetcher")
        self.assertNotIn("secret-token", runs[0]["error_message_sanitized"])
        self.assertTrue(runs[1]["success"])
        self.assertEqual(runs[1]["record_count"], 1)

    def test_realtime_quote_provider_run_records_success(self) -> None:
        manager = DataFetcherManager(fetchers=[_EfinanceRealtimeFetcher()])
        config = SimpleNamespace(
            enable_realtime_quote=True,
            realtime_source_priority="efinance",
        )
        token = activate_run_diagnostic_context(
            trace_id="trace-realtime",
            query_id="query-realtime",
            stock_code="600519",
            trigger_source="api",
        )
        try:
            with patch("src.config.get_config", return_value=config):
                quote = manager.get_realtime_quote("600519")
            snapshot = current_diagnostic_snapshot()
        finally:
            reset_run_diagnostic_context(token)

        self.assertIsNotNone(quote)
        runs = snapshot["provider_runs"]
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["data_type"], "realtime_quote")
        self.assertEqual(runs[0]["provider"], "EfinanceFetcher")
        self.assertTrue(runs[0]["success"])

    def test_record_provider_run_sanitizes_sensitive_text(self) -> None:
        token = activate_run_diagnostic_context(trace_id="trace-secret")
        try:
            record_provider_run(
                data_type="daily_data",
                provider="UnitFetcher",
                operation="get_daily_data",
                success=False,
                error_type="RuntimeError",
                error_message="failed token=secret https://example.com/webhook?key=abc",
            )
            snapshot = current_diagnostic_snapshot()
        finally:
            reset_run_diagnostic_context(token)

        message = snapshot["provider_runs"][0]["error_message_sanitized"]
        self.assertNotIn("secret", message)
        self.assertNotIn("example.com/webhook", message)


if __name__ == "__main__":
    unittest.main()
