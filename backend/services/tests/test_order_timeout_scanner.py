from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.services.trade.models.enums import OrderSide, OrderStatus, TradingMode
from backend.services.trade.services import order_timeout_scanner


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return list(self._values)


class _FakeSession:
    def __init__(self, orders):
        self.orders = list(orders)
        self.committed = False

    async def execute(self, _stmt):
        return _ScalarResult(self.orders)

    async def commit(self):
        self.committed = True


class _FakeSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_bridge_ack_timeout_marks_pending_review_without_rejecting(monkeypatch):
    order = SimpleNamespace(
        order_id=uuid4(),
        tenant_id="default",
        user_id=1001,
        symbol="600000.SH",
        side=OrderSide.BUY,
        trading_mode=TradingMode.REAL,
        status=OrderStatus.SUBMITTED,
        submitted_at=datetime.now() - timedelta(seconds=300),
        exchange_order_id=None,
        remarks="[AWAITING_BRIDGE_ACK]",
    )
    session = _FakeSession([order])
    notifications = []

    monkeypatch.setattr(
        "backend.services.trade.services.order_timeout_scanner.get_session",
        lambda: _FakeSessionContext(session),
    )

    async def _fake_notification(**kwargs):
        notifications.append(kwargs)
        return None

    monkeypatch.setattr(order_timeout_scanner, "publish_notification_async", _fake_notification)
    monkeypatch.setattr(order_timeout_scanner, "_BRIDGE_ACK_TIMEOUT_SECONDS", 120)

    count = await order_timeout_scanner._scan_bridge_ack_timeout_once()

    assert count == 1
    assert session.committed is True
    assert order.status == OrderStatus.SUBMITTED
    assert "[BRIDGE_ACK_TIMEOUT_PENDING_REVIEW]" in (order.remarks or "")
    assert notifications[0]["title"] == "桥接回报超时待核查"


@pytest.mark.asyncio
async def test_bridge_ack_timeout_skips_already_flagged_order(monkeypatch):
    order = SimpleNamespace(
        order_id=uuid4(),
        tenant_id="default",
        user_id=1001,
        symbol="600000.SH",
        side=OrderSide.BUY,
        trading_mode=TradingMode.REAL,
        status=OrderStatus.SUBMITTED,
        submitted_at=datetime.now() - timedelta(seconds=300),
        exchange_order_id=None,
        remarks="[AWAITING_BRIDGE_ACK] [BRIDGE_ACK_TIMEOUT_PENDING_REVIEW]",
    )
    session = _FakeSession([])
    notifications = []

    monkeypatch.setattr(
        "backend.services.trade.services.order_timeout_scanner.get_session",
        lambda: _FakeSessionContext(session),
    )

    async def _fake_notification(**kwargs):
        notifications.append(kwargs)
        return None

    monkeypatch.setattr(order_timeout_scanner, "publish_notification_async", _fake_notification)
    monkeypatch.setattr(order_timeout_scanner, "_BRIDGE_ACK_TIMEOUT_SECONDS", 120)

    count = await order_timeout_scanner._scan_bridge_ack_timeout_once()

    assert count == 0
    assert notifications == []
