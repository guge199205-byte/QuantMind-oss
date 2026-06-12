"""Tests for runner.subprocess_runner — request shape, env stripping, _persist_script."""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.services.engine.strategy_lab.runner import subprocess_runner as sr
from backend.services.engine.strategy_lab.runner.result_collector import (
    Metrics,
    RunResult,
    store_result,
)


class FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, bytes] = {}
        self.lists: dict[str, list[bytes]] = {}
        self.hashes: dict[str, dict[bytes, bytes]] = {}

    def set(self, k, v, ex=None):
        if isinstance(v, str):
            v = v.encode()
        self.kv[k] = v

    def get(self, k):
        return self.kv.get(k)

    def rpush(self, k, v):
        if isinstance(v, str):
            v = v.encode()
        self.lists.setdefault(k, []).append(v)

    def expire(self, *a, **k):
        pass

    def hset(self, k, *, mapping):
        h = self.hashes.setdefault(k, {})
        for kk, vv in mapping.items():
            kb = kk.encode() if isinstance(kk, str) else kk
            vb = vv.encode() if isinstance(vv, str) else (str(vv).encode() if not isinstance(vv, bytes) else vv)
            h[kb] = vb


def test_run_request_assigns_run_id():
    r = sr.RunRequest(code="x")
    assert r.run_id and len(r.run_id) >= 8

    r2 = sr.RunRequest(code="x", run_id="custom-123")
    assert r2.run_id == "custom-123"


def test_safe_env_strips_secrets(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("JWT_SECRET_KEY", "supersecret")
    monkeypatch.setenv("REDIS_HOST", "redis")
    env = sr._safe_env()
    assert "DB_PASSWORD" not in env
    assert "JWT_SECRET_KEY" not in env
    assert env.get("REDIS_HOST") == "redis"
    assert env.get("PYTHONUNBUFFERED") == "1"


def test_persist_script_writes_to_redis(monkeypatch):
    fake = FakeRedis()
    import backend.shared.redis_sentinel_client as rc
    monkeypatch.setattr(rc, "get_redis_sentinel_client", lambda: fake)
    req = sr.RunRequest(code="def setup(ctx): pass\n", run_id="abc")
    sr._persist_script(req)
    assert b"def setup(ctx): pass" in fake.kv["qm:lab:script:abc"]


def test_run_sync_returns_failed_when_worker_writes_nothing(monkeypatch):
    """When _run_worker returns rc!=0 and no result is in Redis, run_sync returns a synthetic 'failed'."""
    fake = FakeRedis()
    import backend.shared.redis_sentinel_client as rc
    import backend.services.engine.strategy_lab.runner.progress as prog
    import backend.services.engine.strategy_lab.runner.result_collector as rcoll
    monkeypatch.setattr(rc, "get_redis_sentinel_client", lambda: fake)
    monkeypatch.setattr(prog, "get_redis_sentinel_client", lambda: fake)
    monkeypatch.setattr(rcoll, "get_redis_sentinel_client", lambda: fake)

    async def fake_run_worker(payload, timeout):
        return 9, "", "boom"

    monkeypatch.setattr(sr, "_run_worker", fake_run_worker)

    req = sr.RunRequest(code="def setup(ctx): pass\n", run_id="r1")
    result = asyncio.run(sr.run_sync(req, timeout_sec=1))
    assert result.status == "failed"
    assert "rc=9" in (result.error or "")


def test_run_sync_returns_stored_result(monkeypatch):
    fake = FakeRedis()
    import backend.shared.redis_sentinel_client as rc
    import backend.services.engine.strategy_lab.runner.progress as prog
    import backend.services.engine.strategy_lab.runner.result_collector as rcoll
    monkeypatch.setattr(rc, "get_redis_sentinel_client", lambda: fake)
    monkeypatch.setattr(prog, "get_redis_sentinel_client", lambda: fake)
    monkeypatch.setattr(rcoll, "get_redis_sentinel_client", lambda: fake)

    async def fake_run_worker(payload, timeout):
        # Simulate worker writing the result before returning
        rid = payload["run_id"]
        store_result(
            RunResult(run_id=rid, status="success", metrics=Metrics(cum_return=0.05)),
            redis_client=fake,
        )
        return 0, "", ""

    monkeypatch.setattr(sr, "_run_worker", fake_run_worker)

    req = sr.RunRequest(code="def setup(ctx): pass\n", run_id="r2")
    result = asyncio.run(sr.run_sync(req, timeout_sec=1))
    assert result.status == "success"
    assert result.metrics.cum_return == 0.05


def test_submit_run_returns_run_id_and_schedules_task(monkeypatch):
    fake = FakeRedis()
    import backend.shared.redis_sentinel_client as rc
    import backend.services.engine.strategy_lab.runner.progress as prog
    monkeypatch.setattr(rc, "get_redis_sentinel_client", lambda: fake)
    monkeypatch.setattr(prog, "get_redis_sentinel_client", lambda: fake)

    seen: dict = {}

    async def fake_run_worker(payload, timeout):
        seen["payload"] = payload
        return 0, "", ""

    monkeypatch.setattr(sr, "_run_worker", fake_run_worker)

    async def go():
        req = sr.RunRequest(code="x", run_id="r3")
        rid = await sr.submit_run(req)
        # Yield so the background task runs
        await asyncio.sleep(0.05)
        return rid

    rid = asyncio.run(go())
    assert rid == "r3"
    assert seen["payload"]["run_id"] == "r3"
