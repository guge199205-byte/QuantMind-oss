import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.services.trade.models.order import OrderStatus, TradingMode
from backend.services.trade.services.trading_engine import TradingEngine


class _FakeRedis:
    def delete(self, *_args, **_kwargs):
        return None


class _FakeDb:
    async def commit(self):
        return None

    async def refresh(self, *_args, **_kwargs):
        return None


class _TimeoutBroker:
    async def place_order(self, **_kwargs):
        raise asyncio.TimeoutError()


@pytest.mark.asyncio
async def test_execute_via_broker_timeout_marks_waiting_for_bridge_ack(monkeypatch):
    engine = TradingEngine(db=_FakeDb(), redis=_FakeRedis())

    order = SimpleNamespace(
        order_id=uuid4(),
        tenant_id="default",
        user_id=79311845,
        symbol="600000.SH",
        quantity=100,
        price=10.0,
        side=SimpleNamespace(value="buy"),
        order_type=SimpleNamespace(value="limit"),
        trade_action=None,
        position_side=None,
        is_margin_trade=False,
        trading_mode=TradingMode.REAL,
        client_order_id="cid-001",
        remarks="",
        status=OrderStatus.SUBMITTED,
    )

    calls = []

    async def _capture_transition(target_order, new_status, remarks=None):
        calls.append(
            {
                "order_id": str(target_order.order_id),
                "new_status": new_status,
                "remarks": remarks,
            }
        )
        if remarks:
            target_order.remarks = f"{target_order.remarks or ''} [{new_status.value.upper()}: {remarks}]".strip()
        target_order.status = new_status
        return target_order

    monkeypatch.setattr(engine, "_get_stock_broker", lambda _mode: _TimeoutBroker())
    monkeypatch.setattr(engine.order_service, "transition_order_status", _capture_transition)
    monkeypatch.setattr("backend.services.trade.services.trading_engine._safe_schedule_notification", lambda _coro: None)
    monkeypatch.setattr(
        "backend.services.trade.services.trading_engine.publish_notification_async",
        lambda **_kwargs: object(),
    )

    await engine._execute_via_broker(order, tenant_id="default")

    assert order.status == OrderStatus.SUBMITTED
    assert len(calls) == 1
    assert calls[0]["new_status"] == OrderStatus.SUBMITTED
    assert calls[0]["remarks"] == "下单超时: 状态未知，请在柜台确认"
    assert "[AWAITING_BRIDGE_ACK]" in order.remarks
    assert "[BRIDGE_ACK_TIMEOUT_PENDING_REVIEW]" in order.remarks
