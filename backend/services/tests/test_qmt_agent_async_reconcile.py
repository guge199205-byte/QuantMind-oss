from __future__ import annotations

import time
from types import SimpleNamespace

from tools.qmt_agent.qmt_agent import AgentConfig, QMTClient


class _FakeTrader:
    def __init__(self):
        self._orders = []
        self._trades = []
        self.last_order_args = None
        self.last_async_order_args = None

    def order_stock_async(
        self,
        account,
        symbol,
        op_type,
        quantity,
        price_type,
        price,
        strategy_name,
        remark,
    ):
        self.last_async_order_args = {
            "account": account,
            "symbol": symbol,
            "op_type": op_type,
            "quantity": quantity,
            "price_type": price_type,
            "price": price,
            "strategy_name": strategy_name,
            "remark": remark,
        }
        return 88

    def order_stock(
        self,
        account,
        symbol,
        op_type,
        quantity,
        price_type,
        price,
        strategy_name,
        remark,
    ):
        self.last_order_args = {
            "account": account,
            "symbol": symbol,
            "op_type": op_type,
            "quantity": quantity,
            "price_type": price_type,
            "price": price,
            "strategy_name": strategy_name,
            "remark": remark,
        }
        return 778899

    def query_stock_orders(self, _account, *_args):
        return self._orders

    def query_stock_trades(self, _account):
        return self._trades

    def query_stock_asset(self, _account):
        return SimpleNamespace(cash=100000.0, available_cash=90000.0, total_asset=120000.0, market_value=20000.0)

    def query_stock_positions(self, _account):
        return []

    def query_credit_detail(self, _account):
        return {
            "liabilities": 12000.0,
            "short_market_value": 9800.0,
            "credit_limit": 300000.0,
            "maintenance_margin_ratio": 1.45,
        }

    def query_credit_slo_code(self, _account):
        return [
            {
                "stock_code": "600000.SH",
                "available_amount": 1200,
            }
        ]


def _make_client() -> tuple[QMTClient, _FakeTrader]:
    cfg = AgentConfig(
        api_base_url="http://localhost/api/v1",
        server_url="ws://localhost/ws/bridge",
        access_key="ak",
        secret_key="sk",
        account_id="10001",
        qmt_path="/tmp",
        reconcile_lookback_seconds=60,
        reconcile_max_orders=1,
        reconcile_max_trades=1,
    )
    events: list[dict] = []
    client = QMTClient(cfg, execution_callback=lambda e: events.append(e))
    trader = _FakeTrader()
    client.enabled = True
    client._trader = trader
    client._account = object()
    client._xtconstant = None
    return client, trader


def test_submit_order_async_records_seq_mapping():
    client, _ = _make_client()
    result = client.submit_order_async(
        {
            "client_order_id": "cid-async-1",
            "symbol": "600000.SH",
            "side": "BUY",
            "quantity": 100,
            "order_type": "LIMIT",
            "price": 10.1,
        }
    )
    assert result["status"] == "SUBMITTED"
    assert result["message"].startswith("async order accepted by qmt")
    assert client._resolve_client_order_by_seq(88) == "cid-async-1"


def test_submit_order_async_protect_limit_uses_level1_price():
    client, trader = _make_client()
    client.get_level1_price = lambda symbol, side: 10.0

    result = client.submit_order_async(
        {
            "client_order_id": "cid-protect-limit-1",
            "symbol": "600000.SH",
            "side": "BUY",
            "quantity": 100,
            "order_type": "MARKET",
            "price": 0,
            "agent_price_mode": "protect_limit",
            "protect_price_ratio": 0.002,
        }
    )

    assert result["status"] == "SUBMITTED"
    assert trader.last_async_order_args is not None
    assert trader.last_async_order_args["price_type"] == 0
    assert trader.last_async_order_args["price"] == 10.02


def test_async_order_callback_resolves_client_order_by_seq():
    captured: list[dict] = []
    client, _ = _make_client()
    client._execution_callback = lambda e: captured.append(e)
    client._remember_async_seq(123, "cid-callback-1")

    callback = client._build_callback()
    callback.on_order_stock_async_response(
        SimpleNamespace(
            seq=123,
            order_id=56789,
            stock_code="600000.SH",
        )
    )

    assert len(captured) == 1
    event = captured[0]
    assert event["client_order_id"] == "cid-callback-1"
    assert event["exchange_order_id"] == "56789"
    assert event["status"] == "SUBMITTED"


def test_reconcile_recent_activity_applies_window_and_limits():
    client, trader = _make_client()
    now = int(time.time())

    trader._orders = [
        SimpleNamespace(order_remark="cid-old-order", order_id="1001", stock_code="600001.SH", order_type=23, traded_volume=0, price=9.8, order_status=48, order_time=now - 5000),
        SimpleNamespace(order_remark="cid-newer-order", order_id="1002", stock_code="600002.SH", order_type=23, traded_volume=10, price=10.2, order_status=49, order_time=now - 20),
        SimpleNamespace(order_remark="cid-newest-order", order_id="1003", stock_code="600003.SH", order_type=24, traded_volume=100, price=10.3, order_status=50, order_time=now - 10),
    ]
    trader._trades = [
        SimpleNamespace(order_remark="cid-old-trade", order_id="2001", traded_id="t-old", stock_code="600010.SH", order_type=23, traded_volume=100, traded_price=9.6, traded_time=now - 3000),
        SimpleNamespace(order_remark="cid-newest-trade", order_id="2002", traded_id="t-new", stock_code="600011.SH", order_type=24, traded_volume=200, traded_price=11.2, traded_time=now - 8),
    ]

    events = client.reconcile_recent_activity()

    assert len(events) == 2
    order_events = [e for e in events if e["exchange_trade_id"] is None]
    trade_events = [e for e in events if e["exchange_trade_id"] is not None]
    assert len(order_events) == 1
    assert len(trade_events) == 1
    assert order_events[0]["client_order_id"] == "cid-newest-order"
    assert trade_events[0]["client_order_id"] == "cid-newest-trade"


def test_async_cancel_callback_resolves_client_order_by_seq():
    captured: list[dict] = []
    client, _ = _make_client()
    client._execution_callback = lambda e: captured.append(e)
    client._remember_async_seq(456, "cid-cancel-1")

    callback = client._build_callback()
    callback.on_cancel_order_stock_async_response(
        SimpleNamespace(
            seq=456,
            order_id=998877,
            stock_code="600519.SH",
        )
    )

    assert len(captured) == 1
    event = captured[0]
    assert event["client_order_id"] == "cid-cancel-1"
    assert event["exchange_order_id"] == "998877"
    assert event["status"] == "SUBMITTED"


def test_reconcile_recent_activity_dedups_same_trade_key():
    client, trader = _make_client()
    now = int(time.time())

    trader._orders = []
    trader._trades = [
        SimpleNamespace(
            order_remark="cid-dedup-1",
            order_id="3001",
            traded_id="dup-trade-id",
            stock_code="600111.SH",
            order_type=23,
            traded_volume=100,
            traded_price=10.5,
            traded_time=now - 5,
        ),
        SimpleNamespace(
            order_remark="cid-dedup-1",
            order_id="3001",
            traded_id="dup-trade-id",
            stock_code="600111.SH",
            order_type=23,
            traded_volume=100,
            traded_price=10.5,
            traded_time=now - 4,
        ),
    ]

    events = client.reconcile_recent_activity()
    trade_events = [e for e in events if e["exchange_trade_id"] == "dup-trade-id"]
    assert len(trade_events) == 1


def test_submit_sell_to_open_rejected_when_long_short_disabled():
    client, _ = _make_client()
    client.cfg.enable_short_trading = False
    client.cfg.account_type = "CREDIT"

    result = client.submit_order(
        {
            "client_order_id": "cid-short-1",
            "symbol": "600000.SH",
            "side": "SELL",
            "trade_action": "sell_to_open",
            "position_side": "short",
            "is_margin_trade": True,
            "quantity": 100,
            "order_type": "LIMIT",
            "price": 10.0,
        }
    )
    assert result["status"] == "REJECTED"
    assert result["error_code"] == "LONG_SHORT_NOT_ENABLED"


def test_submit_sell_to_open_rejected_when_quota_insufficient():
    client, trader = _make_client()
    client.cfg.enable_short_trading = True
    client.cfg.account_type = "CREDIT"
    trader.query_credit_slo_code = lambda _account: [{"stock_code": "600000.SH", "available_amount": 10}]

    result = client.submit_order(
        {
            "client_order_id": "cid-short-2",
            "symbol": "600000.SH",
            "side": "SELL",
            "trade_action": "sell_to_open",
            "position_side": "short",
            "is_margin_trade": True,
            "quantity": 100,
            "order_type": "LIMIT",
            "price": 10.0,
        }
    )
    assert result["status"] == "REJECTED"
    assert result["error_code"] == "SHORT_QUOTA_INSUFFICIENT"


def test_submit_sell_to_open_uses_credit_operation_mapping():
    client, trader = _make_client()
    client.cfg.enable_short_trading = True
    client.cfg.account_type = "CREDIT"
    client._xtconstant = SimpleNamespace(
        STOCK_BUY=23,
        STOCK_SELL=24,
        FIX_PRICE=0,
        CREDIT_SLO_SELL=77,
    )

    result = client.submit_order(
        {
            "client_order_id": "cid-short-3",
            "symbol": "600000.SH",
            "side": "SELL",
            "trade_action": "sell_to_open",
            "position_side": "short",
            "is_margin_trade": True,
            "quantity": 100,
            "order_type": "LIMIT",
            "price": 10.0,
        }
    )
    assert result["status"] == "SUBMITTED"
    assert trader.last_order_args is not None
    assert trader.last_order_args["op_type"] == 77


def test_snapshot_includes_credit_fields():
    client, _ = _make_client()
    snap = client.snapshot()
    assert snap["credit_enabled"] is True
    assert float(snap["liabilities"]) == 12000.0
    assert float(snap["short_market_value"]) == 9800.0


def test_order_error_callback_resolves_client_order_by_exchange_mapping():
    captured: list[dict] = []
    client, _ = _make_client()
    client._execution_callback = lambda e: captured.append(e)
    client.bind_exchange_order_id("cid-err-1", "16926164")

    callback = client._build_callback()
    callback.on_order_error(
        SimpleNamespace(
            order_id=16926164,
            error_msg="柜台拒单",
            stock_code="600000.SH",
            order_type=24,
        )
    )

    assert len(captured) == 1
    event = captured[0]
    assert event["client_order_id"] == "cid-err-1"
    assert event["exchange_order_id"] == "16926164"
    assert event["status"] == "REJECTED"


def test_order_error_callback_keeps_exchange_id_when_client_order_id_missing():
    captured: list[dict] = []
    client, _ = _make_client()
    client._execution_callback = lambda e: captured.append(e)

    callback = client._build_callback()
    callback.on_order_error(
        SimpleNamespace(
            order_id=9988,
            error_msg="network reject",
            stock_code="600010.SH",
            order_type=24,
        )
    )

    assert len(captured) == 1
    event = captured[0]
    assert event["client_order_id"] == ""
    assert event["exchange_order_id"] == "9988"
    assert event["status"] == "REJECTED"
