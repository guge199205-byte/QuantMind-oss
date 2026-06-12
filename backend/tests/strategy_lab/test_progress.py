"""Tests for runner.progress — ProgressEvent serialization + Publisher/Reader against a fake Redis."""

from __future__ import annotations

import json

import pytest

from backend.services.engine.strategy_lab.runner.progress import (
    Phase,
    ProgressEvent,
    ProgressPublisher,
    ProgressReader,
    RunStatus,
    events_key,
    meta_key,
)


class FakeRedis:
    def __init__(self) -> None:
        self.lists: dict[str, list[bytes]] = {}
        self.hashes: dict[str, dict[bytes, bytes]] = {}
        self.expired: dict[str, int] = {}

    def rpush(self, k, v):
        if isinstance(v, str):
            v = v.encode("utf-8")
        self.lists.setdefault(k, []).append(v)
        return len(self.lists[k])

    def lrange(self, k, start, end):
        arr = self.lists.get(k, [])
        if end == -1:
            end = len(arr)
        else:
            end = end + 1
        return arr[start:end]

    def hset(self, k, *, mapping):
        h = self.hashes.setdefault(k, {})
        for kk, vv in mapping.items():
            kb = kk.encode() if isinstance(kk, str) else kk
            vb = vv.encode() if isinstance(vv, str) else (str(vv).encode() if not isinstance(vv, (bytes, bytearray)) else vv)
            h[kb] = vb

    def hgetall(self, k):
        return dict(self.hashes.get(k, {}))

    def expire(self, k, ttl):
        self.expired[k] = ttl


def test_progress_event_clamp_and_roundtrip():
    e = ProgressEvent(run_id="r1", phase=Phase.backtest, pct=150.0, message="ok")
    assert e.pct == 100.0
    raw = e.to_json()
    back = ProgressEvent.from_json(raw)
    assert back.run_id == "r1"
    assert back.phase == Phase.backtest


def test_publisher_and_reader_roundtrip():
    fake = FakeRedis()
    pub = ProgressPublisher(run_id="r1", redis_client=fake)
    pub.publish(Phase.boot, 1.0, "booted")
    pub.publish(Phase.backtest, 50.0, "halfway")
    pub.set_status(RunStatus.running, started_at=123.0)

    reader = ProgressReader(run_id="r1", redis_client=fake)
    events = reader.fetch_events()
    assert len(events) == 2
    assert events[0].phase == Phase.boot
    meta = reader.fetch_meta()
    assert meta["status"] == "running"
    assert events_key("r1") in fake.expired
    assert meta_key("r1") in fake.expired


def test_publisher_swallows_redis_failure():
    class Broken:
        def rpush(self, *a, **k): raise RuntimeError("nope")
        def expire(self, *a, **k): raise RuntimeError("nope")
        def hset(self, *a, **k): raise RuntimeError("nope")

    pub = ProgressPublisher(run_id="r1", redis_client=Broken())
    # Should not raise
    pub.publish(Phase.boot, 1.0, "ok")
    pub.set_status(RunStatus.running)


def test_reader_skips_undecodable():
    fake = FakeRedis()
    fake.lists[events_key("r1")] = [b"not json"]
    reader = ProgressReader(run_id="r1", redis_client=fake)
    events = reader.fetch_events()
    assert events == []
