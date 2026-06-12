"""Tests for the Strategy Lab FastAPI router (Day-2 surface)."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services.engine.strategy_lab import routers as routers_mod
from backend.services.engine.strategy_lab.routers import router
from backend.services.engine.strategy_lab.runner.result_collector import (
    Metrics,
    RunResult,
)


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(router)

    async def fake_run_sync(req, **kw):
        return RunResult(
            run_id=req.run_id,
            status="success",
            metrics=Metrics(cum_return=0.123, n_trades=2),
        )

    async def fake_submit(req, **kw):
        return req.run_id

    monkeypatch.setattr(routers_mod, "run_sync", fake_run_sync)
    monkeypatch.setattr(routers_mod, "submit_run", fake_submit)
    return TestClient(app)


def test_post_run_returns_result(client):
    resp = client.post("/strategy-lab/run", json={"code": "def setup(ctx):\n    pass\n"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["metrics"]["cum_return"] == 0.123


def test_post_run_async_returns_run_id(client):
    resp = client.post("/strategy-lab/run/async", json={"code": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert "run_id" in body
    assert body["status"] == "queued"


def test_get_run_result_404_when_missing(client, monkeypatch):
    monkeypatch.setattr(routers_mod, "fetch_result", lambda rid: None)
    resp = client.get("/strategy-lab/run/missing/result")
    assert resp.status_code == 404


def test_get_run_result_200_when_present(client, monkeypatch):
    monkeypatch.setattr(
        routers_mod,
        "fetch_result",
        lambda rid: RunResult(run_id=rid, status="success", metrics=Metrics(cum_return=0.05)),
    )
    resp = client.get("/strategy-lab/run/abc/result")
    assert resp.status_code == 200
    assert resp.json()["run_id"] == "abc"


def test_get_run_status_streams_events(client, monkeypatch):
    """Drain a single SSE response — the stream must emit when a terminal status is set."""
    from backend.services.engine.strategy_lab.runner import progress as progress_mod

    class StubReader:
        def __init__(self, run_id, redis_client=None):
            self.run_id = run_id
            self._calls = 0

        def fetch_events(self, start=0, end=-1):
            self._calls += 1
            if self._calls == 1:
                evt = progress_mod.ProgressEvent(
                    run_id=self.run_id,
                    phase=progress_mod.Phase.backtest,
                    pct=50.0,
                    message="halfway",
                )
                return [evt]
            return []

        def fetch_meta(self):
            if self._calls >= 2:
                return {"status": "success"}
            return {"status": "running"}

    monkeypatch.setattr(routers_mod, "ProgressReader", StubReader)
    with client.stream("GET", "/strategy-lab/run/abc/status") as resp:
        chunks: list[str] = []
        for line in resp.iter_lines():
            if line:
                chunks.append(line)
            if len(chunks) >= 2:
                break
    body = "\n".join(chunks)
    assert "halfway" in body
    assert "final" in body or "success" in body
