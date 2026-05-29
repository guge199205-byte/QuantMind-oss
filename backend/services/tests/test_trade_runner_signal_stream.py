from typing import Any, Dict, List, Tuple

from backend.services.trade.runner import main as runner_main


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http error {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeRedis:
    def __init__(self, records: list[tuple[str, dict[str, str]]]):
        self.records = records
        self.acked: list[str] = []
        self.order_posts: list[dict[str, Any]] = []
        self.exec_events: list[dict[str, str]] = []

    def xreadgroup(self, *args, **kwargs):
        _ = (args, kwargs)
        if not self.records:
            return []
        messages = [(f"1-{idx+1}", fields) for idx, (_, fields) in enumerate(self.records)]
        self.records = []
        return [("qm:signal:stream:default", messages)]

    def xack(self, stream_name: str, group: str, *ack_ids: str):
        _ = (stream_name, group)
        self.acked.extend(list(ack_ids))
        return len(ack_ids)

    def set(self, key: str, value: str, nx: bool, ex: int):
        _ = (key, value, nx, ex)
        return True

    def xadd(self, stream_name: str, fields: dict[str, str], maxlen: int, approximate: bool):
        _ = (stream_name, maxlen, approximate)
        self.exec_events.append(fields)
        return "2-1"

    def xgroup_create(self, stream_name: str, groupname: str, id: str, mkstream: bool):
        _ = (stream_name, groupname, id, mkstream)
        return True


def test_runner_consume_signal_stream_and_post_internal_order(monkeypatch):
    signal_event = {
        "event_type": "signal_created",
        "tenant_id": "default",
        "user_id": "u1",
        "signal_id": "sig-1",
        "client_order_id": "coid-1",
        "symbol": "600519.SH",
        "side": "BUY",
        "quantity": "100",
        "price": "1500",
        "score": "0.12",
    }
    fake_redis = _FakeRedis(records=[("1-1", signal_event)])

    def _fake_get(url: str, headers: dict[str, str], timeout: int):
        assert url.endswith("/sync-account")
        assert headers["X-User-Id"] == "u1"
        _ = timeout
        return _FakeResponse(
            {
                "cash": 10_000_000,
                "total_asset": 10_000_000,
                "positions": {},
            }
        )

    def _fake_post(url: str, json: dict[str, Any], headers: dict[str, str], timeout: int):
        assert url.endswith("/order")
        assert headers["X-User-Id"] == "u1"
        assert json["client_order_id"] == "coid-1"
        fake_redis.order_posts.append(json)
        _ = timeout
        return _FakeResponse(
            {
                "status": "submitted",
                "order_id": "ord-1",
                "execution": "created",
                "result": {"message": "ok"},
            }
        )

    monkeypatch.setattr(runner_main.requests, "get", _fake_get)
    monkeypatch.setattr(runner_main.requests, "post", _fake_post)
    monkeypatch.setattr(runner_main, "_current_local_ts", lambda: 1_710_310_800.0)
    monkeypatch.setattr(runner_main, "_is_rebalance_day", lambda _ts, _cfg: True)
    monkeypatch.setattr(runner_main, "fetch_market_snapshot", lambda _redis: {})
    monkeypatch.setattr(runner_main, "_acquire_idempotency_lock", lambda *_args, **_kwargs: True)

    processed = runner_main.process_cycle(
        user_id="u1",
        tenant_id="default",
        strategy="s1",
        redis_client=fake_redis,  # type: ignore[arg-type]
        exec_config={},
        live_trade_config={
            "enabled_sessions": ["PM"],
            "sell_time": "14:00",
            "buy_time": "14:30",
            "sell_first": False,
            "max_orders_per_cycle": 20,
            "order_type": "LIMIT",
        },
    )

    assert processed is True
    assert len(fake_redis.order_posts) == 1
    assert len(fake_redis.acked) == 1


def test_runner_skip_other_user_signal_and_no_order(monkeypatch):
    signal_event = {
        "event_type": "signal_created",
        "tenant_id": "default",
        "user_id": "u-other",
        "signal_id": "sig-2",
        "client_order_id": "coid-2",
        "symbol": "000001.SZ",
        "side": "BUY",
        "quantity": "200",
        "price": "15",
        "score": "0.03",
    }
    fake_redis = _FakeRedis(records=[("1-1", signal_event)])

    def _forbidden_post(*args, **kwargs):
        raise AssertionError("unexpected order post for mismatched user signal")

    monkeypatch.setattr(runner_main.requests, "post", _forbidden_post)
    monkeypatch.setattr(runner_main.requests, "get", _forbidden_post)
    monkeypatch.setattr(runner_main, "_current_local_ts", lambda: 1_710_310_800.0)
    monkeypatch.setattr(runner_main, "_is_rebalance_day", lambda _ts, _cfg: True)

    processed = runner_main.process_cycle(
        user_id="u1",
        tenant_id="default",
        strategy="s1",
        redis_client=fake_redis,  # type: ignore[arg-type]
        exec_config={},
        live_trade_config={
            "enabled_sessions": ["PM"],
            "sell_time": "14:00",
            "buy_time": "14:30",
            "sell_first": False,
            "max_orders_per_cycle": 20,
            "order_type": "LIMIT",
        },
    )

    assert processed is False
    assert fake_redis.order_posts == []
    assert len(fake_redis.acked) == 1
