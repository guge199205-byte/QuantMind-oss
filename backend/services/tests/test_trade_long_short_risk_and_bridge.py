import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.services.trade.services.broker_client import QMTBridgeBroker, RedisBroker
from backend.services.trade.services.risk_service import RiskService
from tools.qmt_agent.config import _QMT_ORDER_STATUS_MAP


class _FakeRedisClient:
    def __init__(self, store=None):
        self.store = dict(store or {})

    def get(self, key):
        return self.store.get(key)


class _FakeRedis:
    def __init__(self, store=None):
        self.client = _FakeRedisClient(store=store)


class _DummyResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {"ok": True, "dispatched": 1}
        self.text = json.dumps(self._payload, ensure_ascii=False)

    def json(self):
        return self._payload


class _DummyHttpClient:
    def __init__(self):
        self.last_post = None

    async def post(self, url, json=None, headers=None):
        self.last_post = {
            "url": url,
            "json": json,
            "headers": headers,
        }
        return _DummyResp()


@pytest.mark.asyncio
async def test_qmt_bridge_broker_passes_margin_fields():
    broker = QMTBridgeBroker(stream_base_url="http://stream:8003", internal_secret="secret", redis_client=None)
    dummy_client = _DummyHttpClient()
    async def _fake_get_session():
        return dummy_client
    broker._get_session = _fake_get_session

    result = await broker.place_order(
        user_id=1001,
        symbol="600000.SH",
        side="SELL",
        quantity=200,
        order_type="LIMIT",
        price=10.2,
        tenant_id="default",
        client_order_id="cid-001",
        trade_action="sell_to_open",
        position_side="short",
        is_margin_trade=True,
    )

    assert result.success is True
    payload = dummy_client.last_post["json"]["payload"]
    assert payload["trade_action"] == "sell_to_open"
    assert payload["position_side"] == "short"
    assert payload["is_margin_trade"] is True


@pytest.mark.asyncio
async def test_risk_service_rejects_sell_to_open_when_long_short_not_enabled(monkeypatch):
    redis = _FakeRedis()
    svc = RiskService(db=None, redis=redis)

    async def _no_rules(_user_id):
        return []

    monkeypatch.setattr(svc, "get_applicable_rules", _no_rules)
    monkeypatch.setattr(
        "backend.services.trade.services.risk_service.get_margin_stock_pool_service",
        lambda _path: SimpleNamespace(is_margin_eligible=lambda _symbol: True),
    )
    monkeypatch.setattr("backend.services.trade.services.risk_service.settings.ENABLE_MARGIN_TRADING", True)
    monkeypatch.setattr("backend.services.trade.services.risk_service.settings.ENABLE_LONG_SHORT_REAL", False)
    monkeypatch.setattr("backend.services.trade.services.risk_service.settings.LONG_SHORT_WHITELIST_USERS", "1001")

    order = SimpleNamespace(
        symbol="600000.SH",
        order_value=1000.0,
        side=SimpleNamespace(value="sell"),
        trade_action=SimpleNamespace(value="sell_to_open"),
        trading_mode=SimpleNamespace(value="REAL"),
        is_margin_trade=True,
        tenant_id="default",
    )
    result = await svc.check_order_risk(user_id=1001, order=order, portfolio_value=100000.0, available_cash=50000.0)

    assert result["passed"] is False
    assert any(v["rule"] == "LONG_SHORT_NOT_ENABLED" for v in result["violations"])


@pytest.mark.asyncio
async def test_risk_service_rejects_sell_to_open_when_credit_snapshot_unavailable(monkeypatch):
    redis = _FakeRedis()
    svc = RiskService(db=object(), redis=redis)

    async def _no_rules(_user_id):
        return []

    monkeypatch.setattr(svc, "get_applicable_rules", _no_rules)
    monkeypatch.setattr(
        "backend.services.trade.services.risk_service.get_margin_stock_pool_service",
        lambda _path: SimpleNamespace(is_margin_eligible=lambda _symbol: True),
    )
    monkeypatch.setattr("backend.services.trade.services.risk_service.settings.ENABLE_MARGIN_TRADING", True)
    monkeypatch.setattr("backend.services.trade.services.risk_service.settings.ENABLE_LONG_SHORT_REAL", True)
    monkeypatch.setattr("backend.services.trade.services.risk_service.settings.LONG_SHORT_WHITELIST_USERS", "1001")
    monkeypatch.setattr("backend.services.trade.services.risk_service.settings.SHORT_ADMISSION_STRICT", True)
    monkeypatch.setattr(
        "backend.services.trade.routers.real_trading_utils._fetch_latest_real_account_snapshot",
        AsyncMock(return_value=None),
    )

    order = SimpleNamespace(
        symbol="600000.SH",
        order_value=1000.0,
        side=SimpleNamespace(value="sell"),
        trade_action=SimpleNamespace(value="sell_to_open"),
        trading_mode=SimpleNamespace(value="REAL"),
        is_margin_trade=True,
        tenant_id="default",
    )
    result = await svc.check_order_risk(user_id=1001, order=order, portfolio_value=100000.0, available_cash=50000.0)

    assert result["passed"] is False
    assert any(v["rule"] == "CREDIT_ACCOUNT_UNAVAILABLE" for v in result["violations"])


@pytest.mark.asyncio
async def test_risk_service_passes_sell_to_open_when_all_checks_ready(monkeypatch):
    snapshot = {
        "payload_json": {
            "credit_enabled": True,
            "shortable_symbols_count": 120,
            "last_short_check_at": 1700000000,
        }
    }
    redis = _FakeRedis()
    svc = RiskService(db=object(), redis=redis)

    async def _no_rules(_user_id):
        return []

    monkeypatch.setattr(svc, "get_applicable_rules", _no_rules)
    monkeypatch.setattr(
        "backend.services.trade.services.risk_service.get_margin_stock_pool_service",
        lambda _path: SimpleNamespace(is_margin_eligible=lambda _symbol: True),
    )
    monkeypatch.setattr("backend.services.trade.services.risk_service.settings.ENABLE_MARGIN_TRADING", True)
    monkeypatch.setattr("backend.services.trade.services.risk_service.settings.ENABLE_LONG_SHORT_REAL", True)
    monkeypatch.setattr("backend.services.trade.services.risk_service.settings.LONG_SHORT_WHITELIST_USERS", "1001")
    monkeypatch.setattr("backend.services.trade.services.risk_service.settings.SHORT_ADMISSION_STRICT", True)
    monkeypatch.setattr(
        "backend.services.trade.routers.real_trading_utils._fetch_latest_real_account_snapshot",
        AsyncMock(return_value=snapshot),
    )

    order = SimpleNamespace(
        symbol="600000.SH",
        order_value=1000.0,
        side=SimpleNamespace(value="sell"),
        trade_action=SimpleNamespace(value="sell_to_open"),
        trading_mode=SimpleNamespace(value="REAL"),
        is_margin_trade=True,
        tenant_id="default",
    )
    result = await svc.check_order_risk(user_id=1001, order=order, portfolio_value=100000.0, available_cash=50000.0)

    assert result["passed"] is True
    assert result["violations"] == []


@pytest.mark.asyncio
async def test_redis_broker_query_account_uses_pg_snapshot(monkeypatch):
    snapshot_row = {
        "id": 1,
        "tenant_id": "default",
        "user_id": "00001001",
        "account_id": "8886664999",
        "snapshot_at": "2026-04-09T12:03:04",
        "snapshot_date": "2026-04-09",
        "snapshot_month": "2026-04",
        "total_asset": 100000,
        "cash": 50000,
        "market_value": 50000,
        "today_pnl_raw": 0,
        "total_pnl_raw": 0,
        "floating_pnl_raw": 0,
        "source": "qmt_bridge",
        "payload_json": {"positions": [{"symbol": "600000.SH", "volume": 100}]},
    }

    class _FakeResult:
        def mappings(self):
            return self

        def first(self):
            return snapshot_row

    class _FakeSession:
        async def execute(self, *_args, **_kwargs):
            return _FakeResult()

    class _FakeCtx:
        async def __aenter__(self):
            return _FakeSession()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def _fake_get_session(*_args, **_kwargs):
        return _FakeCtx()

    broker = RedisBroker(
        redis_host="localhost",
        redis_port=6379,
        redis_password="",
        hmac_secret="secret",
    )
    monkeypatch.setattr("backend.services.trade.services.broker_client.get_session", _fake_get_session)
    result = await broker.query_account("1001", tenant_id="default")

    assert result["total_asset"] == 100000
    assert result["positions"] == [{"symbol": "600000.SH", "volume": 100}]


@pytest.mark.asyncio
async def test_risk_service_rejects_star_board_buy_lot_less_than_200(monkeypatch):
    redis = _FakeRedis()
    svc = RiskService(db=None, redis=redis)

    async def _no_rules(_user_id):
        return []

    monkeypatch.setattr(svc, "get_applicable_rules", _no_rules)

    order = SimpleNamespace(
        symbol="688031.SH",
        quantity=100,
        order_value=14400.0,
        side=SimpleNamespace(value="buy"),
        trade_action=None,
        trading_mode=SimpleNamespace(value="REAL"),
        is_margin_trade=False,
        tenant_id="default",
    )
    result = await svc.check_order_risk(user_id=1001, order=order, portfolio_value=100000.0, available_cash=50000.0)
    assert result["passed"] is False
    assert any(v["rule"] == "min_lot_size" for v in result["violations"])


def test_qmt_status_mapping_aligns_with_trade_router():
    assert _QMT_ORDER_STATUS_MAP[50] == "SUBMITTED"
    assert _QMT_ORDER_STATUS_MAP[56] == "FILLED"
    assert _QMT_ORDER_STATUS_MAP[57] == "REJECTED"
