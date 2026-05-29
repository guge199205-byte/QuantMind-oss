import json
import pytest
from fastapi import HTTPException
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from backend.services.trade.deps import AuthContext
from backend.services.trade.routers import (
    internal_strategy_bridge as bridge_router,
    real_trading_lifecycle as real_lifecycle,
    real_trading_preflight as real_preflight,
    real_trading_utils as real_utils,
)
from backend.services.trade.services.trading_precheck_service import (
    run_trading_readiness_precheck,
)
import backend.services.trade.services.trading_precheck_service as precheck_service
from backend.services.trade.routers import real_trading_ledger as real_ledger
from backend.services.trade.services.real_account_snapshot_guard import (
    is_inconsistent_zero_total_snapshot,
    is_suspicious_asset_jump,
)


class _FakeMappingResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        if isinstance(self._row, list):
            return self._row[0] if self._row else None
        return self._row

    def all(self):
        if isinstance(self._row, list):
            return self._row
        return [] if self._row is None else [self._row]


class _FakeDb:
    def __init__(self, rows):
        self._rows = list(rows)

    async def execute(self, *_args, **_kwargs):
        if not self._rows:
            raise AssertionError("unexpected execute call")
        return _FakeMappingResult(self._rows.pop(0))

    async def rollback(self):
        return None


class _FakeRedisClient:
    def __init__(self, payload=None):
        self.payload = payload or {}

    def ping(self):
        return True

    def get(self, key):
        return self.payload.get(key)

    def zrevrange(self, *_args, **_kwargs):
        return [("tick", 9999999999.0)]


class _FakeRedisWrapper:
    def __init__(self):
        self.client = _FakeRedisClient()


class _SnapshotResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        if isinstance(self._row, list):
            return self._row[0] if self._row else None
        return self._row

    def scalars(self):
        return self

    def all(self):
        if isinstance(self._row, list):
            return self._row
        return [] if self._row is None else [self._row]


class _SnapshotDb:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    async def execute(self, *_args, **_kwargs):
        return _SnapshotResult(self.snapshot)

    async def rollback(self):
        return None


@pytest.mark.asyncio
async def test_trading_precheck_fails_when_model_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MODELS_PRODUCTION", str(tmp_path / "missing_model_dir"))
    monkeypatch.setenv("INTERNAL_CALL_SECRET", "secret")
    monkeypatch.setattr(
        "backend.services.trade.services.trading_precheck_service._check_stream_series_freshness",
        lambda _redis: (True, "stream_ready"),
    )

    snapshot_row = {
        "id": 1,
        "tenant_id": "default",
        "user_id": "00001001",
        "account_id": "8886664999",
        "snapshot_at": datetime(2026, 4, 9, 12, 3, 4),
        "snapshot_date": date(2026, 4, 9),
        "snapshot_month": "2026-04",
        "total_asset": 21852149.35,
        "cash": 5356712.35,
        "market_value": 16495437.0,
        "today_pnl_raw": 0.0,
        "total_pnl_raw": 852149.35,
        "floating_pnl_raw": 0.0,
        "initial_equity": 21000000.0,
        "day_open_equity": 21500000.0,
        "month_open_equity": 20500000.0,
        "source": "qmt_bridge",
        "payload_json": {"positions": []},
    }

    fake_db = _FakeDb(
        [
            {"ok": 1},
            snapshot_row,
        ]
    )

    result = await run_trading_readiness_precheck(
        fake_db,
        mode="REAL",
        redis_client=_FakeRedisClient(
            {
                "trade:agent:heartbeat:default:00001001": '{"timestamp": 9999999999}',
            }
        ),
        user_id="1001",
        tenant_id="default",
    )

    assert result["passed"] is False
    assert [item["key"] for item in result["items"]] == [
        "redis",
        "db",
        "internal_secret",
        "user_id",
        "signal_pipeline_enabled",
        "latest_signal_run",
        "production_model",
        "inference_database_ready",
        "k8s_and_runner_ready",
        "realtime_market_ready",
        "qmt_agent_online",
    ]
    model_item = next(item for item in result["items"] if item["key"] == "production_model")
    assert model_item["passed"] is False


@pytest.mark.asyncio
async def test_trading_precheck_fails_without_pg_snapshot_even_with_heartbeat(monkeypatch, tmp_path):
    model_dir = tmp_path / "model_qlib"
    model_dir.mkdir(parents=True)
    (model_dir / "model.pkl").write_bytes(b"fake_model")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MODELS_PRODUCTION", str(model_dir))
    monkeypatch.setenv("STRATEGY_RUNNER_IMAGE", "quantmind-ml-runtime:latest")
    monkeypatch.setenv("INTERNAL_CALL_SECRET", "secret")
    monkeypatch.setattr(
        "backend.services.trade.services.trading_precheck_service._check_stream_series_freshness",
        lambda _redis: (True, "stream_ready"),
    )
    monkeypatch.setattr(real_preflight.k8s_manager, "api", object(), raising=False)
    monkeypatch.setattr(real_preflight.k8s_manager, "core_api", object(), raising=False)
    monkeypatch.setattr(
        "backend.services.trade.services.trading_precheck_service.k8s_manager",
        real_preflight.k8s_manager,
    )
    monkeypatch.setattr(
        "backend.services.trade.routers.real_trading_utils._fetch_latest_real_account_snapshot",
        AsyncMock(return_value=None),
    )

    fake_db = _FakeDb(
        [
            {"ok": 1},
        ]
    )

    result = await run_trading_readiness_precheck(
        fake_db,
        mode="REAL",
        redis_client=_FakeRedisClient({"trade:agent:heartbeat:default:00001001": '{"timestamp": 9999999999}'}),
        user_id="1001",
        tenant_id="default",
    )

    qmt_item = next(item for item in result["items"] if item["key"] == "qmt_agent_online")
    assert qmt_item["passed"] is False
    assert "PostgreSQL 实盘账户快照" in qmt_item["detail"]


@pytest.mark.asyncio
async def test_trading_precheck_shadow_skips_qmt(monkeypatch, tmp_path):
    model_dir = tmp_path / "model_qlib"
    model_dir.mkdir(parents=True)
    (model_dir / "model.pkl").write_bytes(b"fake_model")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MODELS_PRODUCTION", str(model_dir))
    monkeypatch.setenv("STRATEGY_RUNNER_IMAGE", "quantmind-ml-runtime:latest")
    monkeypatch.setenv("INTERNAL_CALL_SECRET", "secret")
    monkeypatch.setattr(
        "backend.services.trade.services.trading_precheck_service._check_stream_series_freshness",
        lambda _redis: (True, "stream_ready"),
    )
    monkeypatch.setattr(real_preflight.k8s_manager, "api", object(), raising=False)
    monkeypatch.setattr(real_preflight.k8s_manager, "core_api", object(), raising=False)
    monkeypatch.setattr(
        "backend.services.trade.services.trading_precheck_service.k8s_manager",
        real_preflight.k8s_manager,
    )

    fake_db = _FakeDb([{"ok": 1}])

    result = await run_trading_readiness_precheck(
        fake_db,
        mode="SHADOW",
        redis_client=_FakeRedisClient(),
        user_id="1001",
        tenant_id="default",
    )

    assert result["passed"] is True
    assert all(item["key"] != "qmt_agent_online" for item in result["items"])


@pytest.mark.asyncio
async def test_fetch_latest_real_account_snapshot_returns_ledger_metrics():
    fake_db = _FakeDb(
        [
            {
                "id": 1,
                "tenant_id": "default",
                "user_id": "00001001",
                "account_id": "8886664999",
                "snapshot_at": datetime(2026, 4, 9, 12, 3, 4),
                "snapshot_date": date(2026, 4, 9),
                "snapshot_month": "2026-04",
                "total_asset": 21852149.35,
                "cash": 5356712.35,
                "market_value": 16495437.0,
                "today_pnl_raw": 0.0,
                "total_pnl_raw": 852149.35,
                "floating_pnl_raw": 0.0,
                "initial_equity": 21000000.0,
                "day_open_equity": 21500000.0,
                "month_open_equity": 20500000.0,
                "source": "qmt_bridge",
                "payload_json": {"positions": []},
            }
        ]
    )

    snapshot = await real_utils._fetch_latest_real_account_snapshot(
        fake_db,
        tenant_id="default",
        user_id="1001",
    )

    assert snapshot is not None
    assert snapshot["monthly_pnl"] == pytest.approx(1352149.35, rel=1e-6)
    assert snapshot["daily_return"] == pytest.approx((21852149.35 - 21500000.0) / 21500000.0 * 100.0, rel=1e-6)
    assert snapshot["total_return"] == pytest.approx((21852149.35 - 21000000.0) / 21000000.0 * 100.0, rel=1e-6)


@pytest.mark.asyncio
async def test_account_daily_ledger_route_uses_current_account_id(monkeypatch):
    auth = AuthContext(user_id="1001", tenant_id="default", raw_sub="1001", roles=["user"])
    captured = {}

    async def _fake_latest_snapshot(*_args, **_kwargs):
        return {
            "account_id": "8886664999",
        }

    async def _fake_list_ledgers(*_args, **kwargs):
        captured["account_id"] = kwargs.get("account_id")
        return [
            type(
                "Row",
                (),
                {
                    "account_id": "8886664999",
                    "snapshot_date": date(2026, 4, 9),
                    "last_snapshot_at": datetime(2026, 4, 9, 12, 3, 4),
                    "total_asset": 21852149.35,
                    "cash": 5356712.35,
                    "market_value": 16495437.0,
                    "initial_equity": 21000000.0,
                    "day_open_equity": 21500000.0,
                    "month_open_equity": 20500000.0,
                    "today_pnl_raw": 0.0,
                    "monthly_pnl_raw": 1352149.35,
                    "total_pnl_raw": 852149.35,
                    "floating_pnl_raw": 0.0,
                    "daily_return_pct": 1.64,
                    "total_return_pct": 4.06,
                    "position_count": 76,
                    "source": "qmt_bridge",
                },
            )
        ]

    monkeypatch.setattr(real_ledger, "_fetch_latest_real_account_snapshot", _fake_latest_snapshot)
    monkeypatch.setattr(real_ledger, "list_real_account_daily_ledgers", _fake_list_ledgers)

    result = await real_ledger.get_account_daily_ledger(
        days=7,
        tenant_id=None,
        user_id=None,
        auth=auth,
        db=object(),
    )

    assert captured["account_id"] == "8886664999"
    assert result[0].account_id == "8886664999"


@pytest.mark.asyncio
async def test_start_trading_rejects_real_when_precheck_failed(monkeypatch):
    monkeypatch.setattr(
        real_lifecycle, "_normalize_identity", lambda auth, user_id=None, tenant_id=None: ("1001", "default")
    )
    monkeypatch.setattr(real_lifecycle, "_schedule_user_notification", lambda **_kwargs: None)

    async def _fake_strategy_detail(strategy_id, user_id):
        return {
            "strategy_name": "demo_strategy",
            "execution_config": {"max_buy_drop": -0.03, "stop_loss": -0.08},
            "code": "print('demo')",
        }

    async def _fake_precheck(*_args, **_kwargs):
        return {
            "passed": False,
            "checked_at": "2026-03-10T15:30:00",
            "items": [
                {
                    "key": "production_model",
                    "label": "生产模型存在",
                    "passed": False,
                    "detail": "model missing",
                }
            ],
        }

    monkeypatch.setattr(real_lifecycle, "_resolve_strategy_detail", _fake_strategy_detail)
    monkeypatch.setattr(real_lifecycle, "run_trading_readiness_precheck", _fake_precheck)

    auth = AuthContext(user_id="1001", tenant_id="default", raw_sub="1001", roles=["user"])

    with pytest.raises(HTTPException) as exc:
        await real_lifecycle.start_trading(
            user_id=None,
            strategy_id="1",
            strategy_file=None,
            trading_mode="REAL",
            execution_config=None,
            live_trade_config=None,
            tenant_id=None,
            auth=auth,
            redis=_FakeRedisWrapper(),
            db=object(),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["precheck_failed"] is True
    assert exc.value.detail["items"][0]["key"] == "production_model"


@pytest.mark.asyncio
async def test_start_trading_simulation_requires_readiness_precheck(monkeypatch):
    monkeypatch.setattr(
        real_lifecycle, "_normalize_identity", lambda auth, user_id=None, tenant_id=None: ("1001", "default")
    )
    monkeypatch.setattr(real_lifecycle, "_schedule_user_notification", lambda **_kwargs: None)

    async def _fake_strategy_detail(strategy_id, user_id):
        return {
            "strategy_name": "demo_strategy",
            "execution_config": {"max_buy_drop": -0.03, "stop_loss": -0.08},
            "code": "print('demo')",
        }

    precheck_called = {"value": False}

    async def _fake_precheck(*_args, **_kwargs):
        precheck_called["value"] = True
        return {"passed": False, "checked_at": "2026-03-10T15:30:00", "items": []}

    class _FakeSandboxManager:
        def submit_strategy(self, **_kwargs):
            return "sandbox-run-id"

    monkeypatch.setattr(real_lifecycle, "_resolve_strategy_detail", _fake_strategy_detail)
    monkeypatch.setattr(real_lifecycle, "run_trading_readiness_precheck", _fake_precheck)
    monkeypatch.setitem(
        __import__("sys").modules,
        "backend.services.trade.sandbox.manager",
        type("M", (), {"sandbox_manager": _FakeSandboxManager()})(),
    )

    class _FakeRedisClientWithSet(_FakeRedisClient):
        def __init__(self):
            super().__init__()
            self.writes = {}

        def set(self, key, value):
            self.writes[key] = value

    redis_wrapper = type("R", (), {"client": _FakeRedisClientWithSet()})()
    auth = AuthContext(user_id="1001", tenant_id="default", raw_sub="1001", roles=["user"])

    with pytest.raises(HTTPException) as exc:
        await real_lifecycle.start_trading(
            user_id=None,
            strategy_id="1",
            strategy_file=None,
            trading_mode="SIMULATION",
            execution_config=None,
            live_trade_config=None,
            tenant_id=None,
            auth=auth,
            redis=redis_wrapper,
            db=object(),
        )

    assert exc.value.status_code == 409
    assert precheck_called["value"] is True


@pytest.mark.asyncio
async def test_start_trading_launches_runtime_container(monkeypatch, tmp_path):
    monkeypatch.setattr(
        real_lifecycle, "_normalize_identity", lambda auth, user_id=None, tenant_id=None: ("1001", "default")
    )
    monkeypatch.setattr(real_lifecycle, "_schedule_user_notification", lambda **_kwargs: None)
    monkeypatch.setattr(real_lifecycle, "_schedule_status_writeback", lambda **_kwargs: None)
    monkeypatch.setattr(real_lifecycle, "get_strategy_path", lambda user_id: str(tmp_path / "strategies" / user_id))

    async def _fake_strategy_detail(strategy_id, user_id):
        return {
            "strategy_name": "demo_strategy",
            "execution_config": {"max_buy_drop": -0.03, "stop_loss": -0.08},
            "live_trade_config": {"enabled_sessions": ["PM"], "sell_time": "14:30", "buy_time": "14:45"},
            "code": "print('demo')",
        }

    async def _fake_precheck(*_args, **_kwargs):
        return {"passed": True, "checked_at": "2026-03-10T15:30:00", "items": []}

    monkeypatch.setattr(real_lifecycle, "_resolve_strategy_detail", _fake_strategy_detail)
    monkeypatch.setattr(real_lifecycle, "run_trading_readiness_precheck", _fake_precheck)
    captured = {}

    def _fake_create_deployment(user_id, strategy_file_path, run_id="default", exec_config=None, tenant_id="default", live_trade_config=None, strategy_id=None):
        captured["user_id"] = user_id
        captured["strategy_file_path"] = strategy_file_path
        captured["run_id"] = run_id
        captured["exec_config"] = exec_config
        captured["tenant_id"] = tenant_id
        captured["live_trade_config"] = live_trade_config
        captured["strategy_id"] = strategy_id
        return {"status": "success", "message": "Container demo started"}

    monkeypatch.setattr(real_lifecycle.k8s_manager, "create_deployment", _fake_create_deployment)

    class _FakeRedisClientWithSet(_FakeRedisClient):
        def __init__(self):
            super().__init__()
            self.writes = {}

        def set(self, key, value):
            self.writes[key] = value

        def delete(self, key):
            self.writes.pop(key, None)

    redis_wrapper = type("R", (), {"client": _FakeRedisClientWithSet()})()
    auth = AuthContext(user_id="1001", tenant_id="default", raw_sub="1001", roles=["user"])

    result = await real_lifecycle.start_trading(
        user_id=None,
        strategy_id="1",
        strategy_file=None,
        trading_mode="REAL",
        execution_config=None,
        live_trade_config=None,
        tenant_id=None,
        auth=auth,
        redis=redis_wrapper,
        db=object(),
    )

    assert result["k8s_result"]["status"] == "success"
    assert result["orchestration_mode"] == real_lifecycle.k8s_manager.mode
    assert captured["user_id"] == "1001"
    assert captured["tenant_id"] == "default"
    assert captured["run_id"].startswith("run_")
    assert captured["strategy_file_path"].endswith(".py")
    assert captured["strategy_id"] == "1"

    stored = json.loads(redis_wrapper.client.writes[real_utils._active_strategy_key("default", "1001")])
    assert stored["launch_result"]["status"] == "success"
    assert stored["strategy_name"] == "demo_strategy"


def test_normalize_live_trade_config_accepts_defaults():
    result = real_utils._normalize_live_trade_config({}, real_utils._default_live_trade_config())

    assert result["rebalance_days"] == 3
    assert result["schedule_type"] == "interval"
    assert result["enabled_sessions"] == ["PM"]
    assert result["sell_time"] == "14:30"
    assert result["buy_time"] == "14:45"


def test_normalize_live_trade_config_rejects_invalid_buy_sell_order():
    with pytest.raises(HTTPException) as exc:
        real_utils._normalize_live_trade_config(
            {
                "enabled_sessions": ["PM"],
                "sell_time": "14:45",
                "buy_time": "14:30",
            },
            real_utils._default_live_trade_config(),
        )

    assert exc.value.status_code == 400
    assert "live_trade_config" in str(exc.value.detail)


def test_normalize_live_trade_config_rejects_invalid_rebalance_days():
    with pytest.raises(HTTPException) as exc:
        real_utils._normalize_live_trade_config(
            {
                "rebalance_days": 2,
                "enabled_sessions": ["PM"],
                "sell_time": "14:30",
                "buy_time": "14:45",
            },
            real_utils._default_live_trade_config(),
        )

    assert exc.value.status_code == 400
    assert "rebalance_days" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_trading_precheck_simulation_keeps_base_checks_and_inference_database(monkeypatch, tmp_path):
    model_dir = tmp_path / "model_qlib"
    model_dir.mkdir(parents=True)
    (model_dir / "model.pkl").write_bytes(b"fake_model")
    monkeypatch.setenv("MODELS_PRODUCTION", str(model_dir))
    monkeypatch.setenv("INTERNAL_CALL_SECRET", "secret")
    monkeypatch.setattr(
        "backend.services.trade.services.trading_precheck_service._check_stream_series_freshness",
        lambda _redis: (True, "stream_ready"),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "backend.services.trade.sandbox.manager",
        type(
            "M",
            (),
            {
                "sandbox_manager": type(
                    "SM",
                    (),
                    {
                        "_workers": {
                            "w1": type("P", (), {"is_alive": lambda self: True})(),
                        }
                    },
                )()
            },
        )(),
    )
    fake_db = _FakeDb([{"ok": 1}])

    result = await run_trading_readiness_precheck(
        fake_db,
        mode="SIMULATION",
        redis_client=_FakeRedisClient(),
        user_id="1001",
        tenant_id="default",
    )

    assert result["passed"] is True
    assert [item["key"] for item in result["items"]] == [
        "redis",
        "db",
        "internal_secret",
        "user_id",
        "signal_pipeline_enabled",
        "latest_signal_run",
        "inference_database_ready",
        "simulation_sandbox_pool",
        "realtime_market_ready",
    ]


@pytest.mark.asyncio
async def test_preflight_simulation_includes_inference_database_check(monkeypatch):
    monkeypatch.setattr(real_preflight, "_normalize_identity", lambda auth, user_id=None, tenant_id=None: ("1001", "default"))

    async def _noop_snapshot(*_args, **_kwargs):
        return None

    monkeypatch.setattr(real_preflight, "_upsert_preflight_snapshot", _noop_snapshot)

    fake_db = _FakeDb(
        [
            {"ok": 1},
            {
                "sim_orders": True,
                "sim_trades": True,
                "simulation_fund_snapshots": True,
            },
        ]
    )

    auth = AuthContext(user_id="1001", tenant_id="default", raw_sub="1001", roles=["user"])
    result = await real_preflight.preflight_check(
        trading_mode="SIMULATION",
        user_id=None,
        tenant_id=None,
        auth=auth,
        redis=_FakeRedisWrapper(),
        db=fake_db,
    )

    assert result["mode"] == "SIMULATION"
    assert any(item["key"] == "inference_database_ready" for item in result["checks"])


@pytest.mark.asyncio
async def test_get_account_uses_pg_snapshot_only(monkeypatch):
    from datetime import date, datetime

    monkeypatch.setattr(
        real_preflight,
        "_normalize_identity",
        lambda auth, user_id=None, tenant_id=None: ("00001001", "default"),
    )
    monkeypatch.setattr(
        real_preflight,
        "_fetch_latest_real_account_snapshot",
        AsyncMock(return_value={
            "user_id": "00001001",
            "tenant_id": "default",
            "account_id": "8886664999",
            "snapshot_at": datetime(2026, 4, 9, 12, 3, 4).isoformat(),
            "snapshot_date": date(2026, 4, 9).isoformat(),
            "snapshot_month": "2026-04",
            "total_asset": 21852149.35,
            "available_cash": 5356712.35,
            "cash": 5356712.35,
            "market_value": 16495437.0,
            "today_pnl": 352149.35,
            "daily_pnl": 352149.35,
            "total_pnl": 852149.35,
            "floating_pnl": 0.0,
            "initial_equity": 21000000.0,
            "day_open_equity": 21500000.0,
            "month_open_equity": 20500000.0,
            "is_online": True,
            "source": "qmt_bridge",
            "payload_json": {
                "positions": [
                    {"symbol": "000001.SZ", "volume": 100},
                    {"symbol": "600000.SH", "volume": 200},
                ]
            },
            "positions": [
                {"symbol": "000001.SZ", "volume": 100},
                {"symbol": "600000.SH", "volume": 200},
            ],
            "position_count": 2,
        }),
    )

    auth = AuthContext(user_id="1001", tenant_id="default", raw_sub="1001", roles=["user"])

    result = await real_preflight.get_account(
        tenant_id=None,
        user_id=None,
        auth=auth,
        db=object(),
    )

    assert result["total_asset"] == 21852149.35
    assert result["cash"] == 5356712.35
    assert result["available_cash"] == 5356712.35
    assert result["market_value"] == 16495437.0
    assert result["today_pnl"] == 352149.35
    assert result["positions"] == [
        {"symbol": "000001.SZ", "volume": 100},
        {"symbol": "600000.SH", "volume": 200},
    ]
    assert result["position_count"] == 2
    assert result["source"] == "qmt_bridge"


@pytest.mark.asyncio
async def test_get_account_returns_404_without_pg_snapshot(monkeypatch):
    monkeypatch.setattr(
        real_preflight,
        "_normalize_identity",
        lambda auth, user_id=None, tenant_id=None: ("00001001", "default"),
    )
    monkeypatch.setattr(real_preflight, "_fetch_latest_real_account_snapshot", AsyncMock(return_value=None))

    auth = AuthContext(user_id="1001", tenant_id="default", raw_sub="1001", roles=["user"])
    with pytest.raises(HTTPException) as exc:
        await real_preflight.get_account(
            tenant_id=None,
            user_id=None,
            auth=auth,
            db=object(),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_fetch_latest_real_account_snapshot_prefers_view_row():
    from datetime import date, datetime

    row = {
        "id": 123,
        "tenant_id": "default",
        "user_id": "00001001",
        "account_id": "8886664999",
        "snapshot_at": datetime(2026, 4, 9, 12, 3, 4),
        "snapshot_date": date(2026, 4, 9),
        "snapshot_month": "2026-04",
        "total_asset": 21852149.35,
        "cash": 5356712.35,
        "market_value": 16495437.0,
        "today_pnl_raw": 0.0,
        "total_pnl_raw": 852149.35,
        "floating_pnl_raw": 0.0,
        "initial_equity": 21000000.0,
        "day_open_equity": 21500000.0,
        "month_open_equity": 20500000.0,
        "source": "qmt_bridge",
        "payload_json": {"positions": [{"symbol": "000001.SZ", "volume": 1}]},
    }

    snapshot = await real_utils._fetch_latest_real_account_snapshot(
        _FakeDb([row]),
        tenant_id="default",
        user_id="1001",
    )

    assert snapshot is not None
    assert snapshot["account_id"] == "8886664999"
    assert snapshot["cash"] == 5356712.35
    assert snapshot["initial_equity"] == 21000000.0
    assert snapshot["day_open_equity"] == 21500000.0
    assert snapshot["month_open_equity"] == 20500000.0
    assert snapshot["position_count"] == 1
    assert snapshot["positions"] == [{"symbol": "000001.SZ", "volume": 1}]


@pytest.mark.asyncio
async def test_fetch_latest_real_account_snapshot_skips_empty_tail_row():
    from datetime import date, datetime

    rows = [
        {
            "id": 124,
            "tenant_id": "default",
            "user_id": "00001001",
            "account_id": "8886664999",
            "snapshot_at": datetime(2026, 4, 9, 12, 4, 4),
            "snapshot_date": date(2026, 4, 9),
            "snapshot_month": "2026-04",
            "total_asset": 0.0,
            "cash": 0.0,
            "market_value": 0.0,
            "today_pnl_raw": 0.0,
            "total_pnl_raw": 0.0,
            "floating_pnl_raw": 0.0,
            "initial_equity": 21000000.0,
            "day_open_equity": 21500000.0,
            "month_open_equity": 20500000.0,
            "source": "qmt_bridge",
            "payload_json": {"positions": []},
        },
        {
            "id": 123,
            "tenant_id": "default",
            "user_id": "00001001",
            "account_id": "8886664999",
            "snapshot_at": datetime(2026, 4, 9, 12, 3, 4),
            "snapshot_date": date(2026, 4, 9),
            "snapshot_month": "2026-04",
            "total_asset": 21852149.35,
            "cash": 5356712.35,
            "market_value": 16495437.0,
            "today_pnl_raw": 0.0,
            "total_pnl_raw": 852149.35,
            "floating_pnl_raw": 0.0,
            "initial_equity": 21000000.0,
            "day_open_equity": 21500000.0,
            "month_open_equity": 20500000.0,
            "source": "qmt_bridge",
            "payload_json": {"positions": [{"symbol": "000001.SZ", "volume": 1}]},
        },
    ]

    snapshot = await real_utils._fetch_latest_real_account_snapshot(
        _FakeDb([rows]),
        tenant_id="default",
        user_id="1001",
    )

    assert snapshot is not None
    assert snapshot["total_asset"] == 21852149.35
    assert snapshot["position_count"] == 1


@pytest.mark.asyncio
async def test_fetch_real_account_baseline_returns_manual_override():
    row = {
        "initial_equity": 21000000.0,
        "first_snapshot_at": datetime(2026, 4, 7, 11, 0, 11, 386412),
        "source": "manual_override",
    }

    baseline = await real_utils._fetch_real_account_baseline(
        _FakeDb([row]),
        tenant_id="default",
        user_id="79311845",
        account_id="8886664999",
    )

    assert baseline is not None
    assert baseline["initial_equity"] == 21000000.0
    assert baseline["source"] == "manual_override"


@pytest.mark.asyncio
async def test_get_account_marks_snapshot_offline_when_stale(monkeypatch):
    old_snapshot = {
        "snapshot_at": "2026-04-09T10:00:00+00:00",
        "cash": 100.0,
        "available_cash": 100.0,
        "total_asset": 200.0,
        "market_value": 100.0,
        "initial_equity": 150.0,
        "day_open_equity": 190.0,
        "month_open_equity": 180.0,
    }
    fixed_now = datetime(2026, 4, 11, 11, 0, 0, tzinfo=timezone.utc).timestamp()

    monkeypatch.setattr(
        real_preflight,
        "_normalize_identity",
        lambda auth, user_id=None, tenant_id=None: ("00001001", "default"),
    )
    monkeypatch.setattr(real_preflight, "_fetch_latest_real_account_snapshot", AsyncMock(return_value=old_snapshot))
    monkeypatch.setattr(real_preflight.time, "time", lambda: fixed_now)
    monkeypatch.setenv("QMT_AGENT_ACCOUNT_STALE_THRESHOLD_SEC", "120")

    auth = AuthContext(user_id="1001", tenant_id="default", raw_sub="1001", roles=["user"])
    result = await real_preflight.get_account(
        tenant_id=None,
        user_id=None,
        auth=auth,
        db=object(),
    )

    assert result["is_online"] is False
    assert "stale_reason" in result


@pytest.mark.asyncio
async def test_qmt_agent_online_treats_naive_snapshot_timestamp_as_utc(monkeypatch):
    snapshot_at = datetime.fromtimestamp(1_700_000_000)
    heartbeat_ts = 1_700_000_010
    account_snapshot = {
        "snapshot_at": snapshot_at,
    }

    monkeypatch.setattr(
        "backend.services.trade.routers.real_trading_utils._fetch_latest_real_account_snapshot",
        AsyncMock(return_value=account_snapshot),
    )
    monkeypatch.setattr(precheck_service.time, "time", lambda: heartbeat_ts)

    ok, detail = await precheck_service._check_qmt_agent_online(
        _FakeDb([{"ok": 1}]),
        _FakeRedisClient({"trade:agent:heartbeat:default:00001001": f'{{"timestamp": {heartbeat_ts}}}'}),
        "default",
        "1001",
    )

    assert ok is True
    assert "account_age_sec=" in detail


@pytest.mark.asyncio
async def test_bridge_account_uses_latest_valid_snapshot_for_portfolio_sync_when_guard_rejects(monkeypatch):
    payload = bridge_router.QMTBridgeAccountPayload(
        account_id="8886664999",
        total_asset=0.0,
        cash=0.0,
        available_cash=0.0,
        market_value=0.0,
        positions=[],
        reported_at=datetime(2026, 4, 11, 10, 0, 0, tzinfo=timezone.utc),
    )
    metrics = {
        "today_pnl": 0.0,
        "total_pnl": 0.0,
        "floating_pnl": 0.0,
        "monthly_pnl": 0.0,
        "total_return": 0.0,
        "win_rate": 0.0,
    }
    metrics_meta = {
        "snapshot_persisted": False,
        "snapshot_reject_reason": "rejected_empty_snapshot",
        "quality": "ok",
    }
    latest_snapshot = {
        "snapshot_at": "2026-04-11T09:59:30+00:00",
        "cash": 5356712.35,
        "available_cash": 5356712.35,
        "total_asset": 21852149.35,
        "market_value": 16495437.0,
        "today_pnl": 0.0,
        "total_pnl": 852149.35,
        "floating_pnl": 0.0,
        "monthly_pnl": 852149.35,
        "total_return": 4.057854,
        "baseline": {
            "initial_equity": 21000000.0,
            "day_open_equity": 21852149.35,
            "month_open_equity": 21000000.0,
        },
        "positions": [{"symbol": "000001.SZ", "volume": 100, "symbol_name": "平安银行"}],
        "position_count": 1,
        "payload_json": {
            "positions": [{"symbol": "000001.SZ", "volume": 100, "symbol_name": "平安银行"}],
            "liabilities": 123.0,
            "short_market_value": 45.0,
        },
    }

    captured_cache = {}
    sync_mock = AsyncMock()
    monkeypatch.setattr(bridge_router, "_compute_account_metrics", AsyncMock(return_value=(metrics, metrics_meta)))
    monkeypatch.setattr(bridge_router, "_fetch_latest_real_account_snapshot", AsyncMock(return_value=latest_snapshot))
    monkeypatch.setattr(bridge_router, "_sync_qmt_account_to_db", sync_mock)
    monkeypatch.setattr(bridge_router, "write_trade_account_cache", lambda _redis, _tenant, _user, info: captured_cache.update(info))

    class _FakeRedis:
        def publish_event(self, *_args, **_kwargs):
            return None

    class _FakeDb:
        async def commit(self):
            return None

    ctx = SimpleNamespace(tenant_id="default", user_id="00001001", account_id="8886664999")
    result = await bridge_router.upsert_qmt_account_snapshot(
        payload=payload,
        ctx=ctx,
        redis=_FakeRedis(),
        db=_FakeDb(),
    )

    assert result["ok"] is True
    sync_mock.assert_awaited_once()
    sync_kwargs = sync_mock.await_args.kwargs
    assert sync_kwargs["total_asset"] == 21852149.35
    assert sync_kwargs["available_cash"] == 5356712.35
    assert sync_kwargs["position_rows"] == [{"symbol": "000001.SZ", "volume": 100, "symbol_name": "平安银行"}]
    assert captured_cache["snapshot_guard_triggered"] is True
    assert captured_cache["metrics_meta"]["quality"] == "guard_rejected"
    assert captured_cache["metrics_meta"]["snapshot_guard"]["fallback_sync_source"] == "latest_valid_snapshot"


@pytest.mark.asyncio
async def test_bridge_account_skips_portfolio_sync_when_guard_rejects_and_no_fallback(monkeypatch):
    payload = bridge_router.QMTBridgeAccountPayload(
        account_id="8886664999",
        total_asset=0.0,
        cash=0.0,
        available_cash=0.0,
        market_value=0.0,
        positions=[],
        reported_at=datetime(2026, 4, 11, 10, 0, 0, tzinfo=timezone.utc),
    )
    metrics = {
        "today_pnl": 0.0,
        "total_pnl": 0.0,
        "floating_pnl": 0.0,
        "monthly_pnl": 0.0,
        "total_return": 0.0,
        "win_rate": 0.0,
    }
    metrics_meta = {
        "snapshot_persisted": False,
        "snapshot_reject_reason": "rejected_empty_snapshot",
        "quality": "ok",
    }

    sync_mock = AsyncMock()
    monkeypatch.setattr(bridge_router, "_compute_account_metrics", AsyncMock(return_value=(metrics, metrics_meta)))
    monkeypatch.setattr(bridge_router, "_fetch_latest_real_account_snapshot", AsyncMock(return_value=None))
    monkeypatch.setattr(bridge_router, "_sync_qmt_account_to_db", sync_mock)
    cache_mock = AsyncMock()
    monkeypatch.setattr(bridge_router, "write_trade_account_cache", cache_mock)

    class _FakeRedis:
        def publish_event(self, *_args, **_kwargs):
            return None

    class _FakeDb:
        async def commit(self):
            return None

    ctx = SimpleNamespace(tenant_id="default", user_id="00001001", account_id="8886664999")
    result = await bridge_router.upsert_qmt_account_snapshot(
        payload=payload,
        ctx=ctx,
        redis=_FakeRedis(),
        db=_FakeDb(),
    )

    assert result["ok"] is True
    sync_mock.assert_not_awaited()
    cache_mock.assert_not_awaited()


def test_snapshot_guard_detects_suspicious_asset_jump_with_positions():
    assert is_suspicious_asset_jump(
        total_asset=2_000_000,
        cash=500_000,
        market_value=0.0,
        prev_total_asset=21_000_000,
        prev_cash=5_000_000,
        prev_market_value=16_000_000,
        payload_json={"positions": [{"symbol": "000001.SZ", "volume": 100}]},
    ) is True


def test_snapshot_guard_rejects_zero_total_with_nonempty_assets():
    assert is_inconsistent_zero_total_snapshot(
        total_asset=0.0,
        cash=0.0,
        market_value=19_422_490.0,
        payload_json={"positions": [{"symbol": "000001.SZ", "volume": 100}]},
    )
    assert is_inconsistent_zero_total_snapshot(
        total_asset=0.0,
        cash=12.0,
        market_value=0.0,
        payload_json={"positions": []},
    )
    assert not is_inconsistent_zero_total_snapshot(
        total_asset=0.0,
        cash=0.0,
        market_value=0.0,
        payload_json={"positions": []},
    )


def test_snapshot_guard_allows_liquidation_into_cash():
    assert is_suspicious_asset_jump(
        total_asset=21_000_000,
        cash=21_000_000,
        market_value=0.0,
        prev_total_asset=21_000_000,
        prev_cash=5_000_000,
        prev_market_value=16_000_000,
        payload_json={"positions": []},
    ) is False


@pytest.mark.asyncio
async def test_account_daily_ledger_exposes_settlement_metadata(monkeypatch):
    class _Row:
        account_id = "8886664999"
        snapshot_date = date(2026, 4, 11)
        last_snapshot_at = datetime(2026, 4, 11, 7, 5, 0)
        total_asset = 21852149.35
        cash = 5356712.35
        market_value = 16495437.0
        initial_equity = 21000000.0
        day_open_equity = 21800000.0
        month_open_equity = 21000000.0
        today_pnl_raw = 1234.0
        monthly_pnl_raw = 852149.35
        total_pnl_raw = 852149.35
        floating_pnl_raw = 100.0
        daily_return_pct = 0.24
        total_return_pct = 4.05
        position_count = 3
        source = "daily_settlement"
        payload_json = {
            "settlement_finalized": True,
            "settlement_finalized_at": "2026-04-11T07:00:00+00:00",
            "settlement_snapshot_count": 12,
        }

    auth = AuthContext(user_id="1001", tenant_id="default", raw_sub="1001", roles=["user"])
    monkeypatch.setattr(
        real_ledger,
        "_normalize_identity",
        lambda auth, user_id=None, tenant_id=None: ("00001001", "default"),
    )
    monkeypatch.setattr(
        real_ledger,
        "_fetch_latest_real_account_snapshot",
        AsyncMock(return_value={"account_id": "8886664999"}),
    )
    monkeypatch.setattr(
        real_ledger,
        "list_real_account_daily_ledgers",
        AsyncMock(return_value=[_Row()]),
    )

    result = await real_ledger.get_account_daily_ledger(
        days=30,
        tenant_id=None,
        user_id=None,
        auth=auth,
        db=object(),
    )

    assert len(result) == 1
    assert result[0].settlement_finalized is True
    assert result[0].settlement_finalized_at == "2026-04-11T07:00:00+00:00"
    assert result[0].settlement_snapshot_count == 12
