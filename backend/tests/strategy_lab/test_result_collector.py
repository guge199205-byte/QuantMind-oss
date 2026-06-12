"""Tests for runner.result_collector — sanitization, repro hash, Redis store/fetch."""

from __future__ import annotations

import json

from backend.services.engine.strategy_lab.runner.result_collector import (
    EquityPoint,
    Metrics,
    PositionSnapshot,
    RunResult,
    TradeRecord,
    _sanitize,
    compute_script_sha,
    fetch_result,
    store_result,
)


class FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, bytes] = {}

    def set(self, k, v, ex=None):
        if isinstance(v, str):
            v = v.encode("utf-8")
        self.kv[k] = v

    def get(self, k):
        return self.kv.get(k)


def test_sanitize_drops_nan_inf():
    out = _sanitize(
        {
            "a": float("nan"),
            "b": float("inf"),
            "c": [1.0, float("-inf"), {"d": float("nan")}],
            "e": "ok",
        }
    )
    assert out["a"] is None
    assert out["b"] is None
    assert out["c"][1] is None
    assert out["c"][2]["d"] is None
    assert out["e"] == "ok"


def test_runresult_to_dict_and_to_json_drops_nan():
    r = RunResult(
        run_id="r1",
        status="success",
        metrics=Metrics(cum_return=float("nan"), sharpe=1.5),
        equity=[EquityPoint(date="2025-01-01", value=1.0, benchmark=float("inf"))],
    )
    d = r.to_dict()
    assert d["metrics"]["cum_return"] is None
    assert d["metrics"]["sharpe"] == 1.5
    assert d["equity"][0]["benchmark"] is None
    # round-trip JSON
    parsed = json.loads(r.to_json())
    assert parsed["status"] == "success"


def test_runresult_from_dict_roundtrip():
    r = RunResult(
        run_id="r1",
        status="success",
        metrics=Metrics(cum_return=0.1),
        equity=[EquityPoint(date="2025-01-01", value=1.0)],
        trades=[TradeRecord(date="2025-01-02", symbol="SH600036", direction="BUY", price=10.0, qty=100)],
        positions=[PositionSnapshot(date="2025-01-02", symbol="SH600036", qty=100, cost=1000, market_value=1100, pnl_pct=0.1)],
    )
    raw = r.to_json()
    back = RunResult.from_dict(json.loads(raw))
    assert back.metrics.cum_return == 0.1
    assert back.trades[0].symbol == "SH600036"
    assert back.positions[0].qty == 100


def test_compute_script_sha_is_deterministic_and_param_sensitive():
    code = "def setup(ctx):\n    pass\n"
    h1 = compute_script_sha(code, {"a": 1, "b": 2})
    h2 = compute_script_sha(code, {"b": 2, "a": 1})  # order shouldn't matter
    assert h1 == h2
    h3 = compute_script_sha(code, {"a": 1, "b": 3})
    assert h1 != h3


def test_store_and_fetch_result_via_fake_redis():
    fake = FakeRedis()
    r = RunResult(run_id="r1", status="success", metrics=Metrics(cum_return=0.05))
    store_result(r, redis_client=fake)
    back = fetch_result("r1", redis_client=fake)
    assert back is not None
    assert back.run_id == "r1"
    assert back.metrics.cum_return == 0.05


def test_fetch_result_missing_returns_none():
    fake = FakeRedis()
    assert fetch_result("nope", redis_client=fake) is None


def test_fetch_result_decode_error_returns_none():
    fake = FakeRedis()
    fake.kv["qm:lab:result:r1"] = b"not json"
    assert fetch_result("r1", redis_client=fake) is None
