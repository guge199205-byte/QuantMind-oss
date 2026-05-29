from datetime import datetime, timezone
from uuid import uuid4

from backend.services.trade.models.order import OrderSide, OrderStatus, OrderType, PositionSide, TradeAction, TradingMode
from backend.services.trade.schemas.order import OrderResponse
from backend.services.trade.schemas.trade import TradeResponse


def test_trade_response_serializes_naive_datetimes_as_utc_iso():
    payload = TradeResponse(
        id=1,
        trade_id=uuid4(),
        order_id=uuid4(),
        tenant_id="default",
        user_id=79311845,
        portfolio_id=1,
        symbol="600519.SH",
        side=OrderSide.BUY,
        trade_action=TradeAction.BUY_TO_OPEN,
        position_side=PositionSide.LONG,
        is_margin_trade=False,
        trading_mode=TradingMode.REAL,
        quantity=14,
        price=100.0,
        trade_value=1400.0,
        commission=1.2,
        executed_at=datetime(2026, 4, 9, 5, 12, 0),
        exchange_trade_id="EX-1",
        exchange_name="SSE",
        remarks=None,
        created_at=datetime(2026, 4, 9, 5, 12, 1),
        updated_at=datetime(2026, 4, 9, 5, 12, 2),
    )

    dumped = payload.model_dump(mode="json")
    assert dumped["executed_at"] == "2026-04-09T05:12:00+00:00"
    assert dumped["created_at"] == "2026-04-09T05:12:01+00:00"
    assert dumped["updated_at"] == "2026-04-09T05:12:02+00:00"


def test_order_response_serializes_naive_datetimes_as_utc_iso():
    payload = OrderResponse(
        symbol="600519.SH",
        symbol_name="贵州茅台",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=14,
        price=100.0,
        stop_price=None,
        trade_action=TradeAction.BUY_TO_OPEN,
        position_side=PositionSide.LONG,
        is_margin_trade=False,
        client_order_id="client-1",
        remarks=None,
        id=1,
        order_id=uuid4(),
        tenant_id="default",
        user_id=79311845,
        portfolio_id=1,
        strategy_id=None,
        trading_mode=TradingMode.REAL,
        status=OrderStatus.FILLED,
        filled_quantity=14,
        average_price=100.0,
        order_value=1400.0,
        filled_value=1400.0,
        commission=1.2,
        submitted_at=datetime(2026, 4, 9, 5, 12, 0),
        filled_at=datetime(2026, 4, 9, 5, 12, 1, tzinfo=timezone.utc),
        cancelled_at=None,
        expired_at=None,
        exchange_order_id="EX-1",
        created_at=datetime(2026, 4, 9, 5, 11, 59),
        updated_at=datetime(2026, 4, 9, 5, 12, 2),
    )

    dumped = payload.model_dump(mode="json")
    assert dumped["submitted_at"] == "2026-04-09T05:12:00+00:00"
    assert dumped["filled_at"] == "2026-04-09T05:12:01+00:00"
    assert dumped["created_at"] == "2026-04-09T05:11:59+00:00"
    assert dumped["updated_at"] == "2026-04-09T05:12:02+00:00"
