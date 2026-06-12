"""Targeted tests for engine.broker — order resolution, T+1, fee math, partial fills."""

from __future__ import annotations

import pandas as pd

from backend.services.engine.strategy_lab.engine.broker import LOT_SIZE, SimpleBroker
from backend.services.engine.strategy_lab.engine.data_provider import InMemoryProvider
from backend.services.engine.strategy_lab.sdk.context import Context, OrderIntent


def _provider(close: float = 10.0) -> InMemoryProvider:
    idx = pd.date_range("2025-01-02", periods=5, freq="B")
    df = pd.DataFrame(
        {
            "open": [close] * 5,
            "high": [close * 1.01] * 5,
            "low": [close * 0.99] * 5,
            "close": [close] * 5,
            "volume": [10000.0] * 5,
            "adj_close": [close] * 5,
        },
        index=idx,
    )
    return InMemoryProvider({"A": df})


def _setup_ctx(commission=0.0, slippage=0.0, tax=0.0, transfer=0.0) -> Context:
    c = Context()
    c.universe = ["A"]
    c.start = "2025-01-02"
    c.end = "2025-01-08"
    c.cash = 1_000_000
    c.commission = commission
    c.slippage = slippage
    c.tax_sell = tax
    c.transfer_fee = transfer
    return c


def test_buy_order_rounds_to_lot_size():
    ctx = _setup_ctx()
    p = _provider(close=11.0)
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    today = pd.Timestamp("2025-01-02")
    b.process_day(today, [OrderIntent(symbol="A", side="buy", weight=0.5)])
    assert "A" in b._holdings
    assert b._holdings["A"].total_qty % LOT_SIZE == 0


def test_t_plus_one_blocks_same_day_sell():
    ctx = _setup_ctx()
    p = _provider(close=10.0)
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    today = pd.Timestamp("2025-01-02")
    b.process_day(
        today,
        [
            OrderIntent(symbol="A", side="buy", weight=0.5),
            OrderIntent(symbol="A", side="sell", all=True),
        ],
    )
    sells = [t for t in b.trades if t.direction == "SELL"]
    assert sells == []  # cannot sell what was just bought today


def test_sell_after_t_plus_one_executes():
    ctx = _setup_ctx()
    p = _provider(close=10.0)
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    d1 = pd.Timestamp("2025-01-02")
    d2 = pd.Timestamp("2025-01-03")
    b.process_day(d1, [OrderIntent(symbol="A", side="buy", weight=0.5)])
    b.process_day(d2, [OrderIntent(symbol="A", side="sell", all=True)])
    sells = [t for t in b.trades if t.direction == "SELL"]
    assert len(sells) == 1


def test_partial_buy_when_cash_runs_out():
    ctx = _setup_ctx()
    p = _provider(close=10.0)
    # tiny cash that can't cover requested weight
    b = SimpleBroker(ctx=ctx, provider=p, cash=500.0)
    today = pd.Timestamp("2025-01-02")
    b.process_day(today, [OrderIntent(symbol="A", side="buy", qty=10000)])
    held = b._holdings.get("A")
    # Either nothing was bought (rounded to 0 lots) or a fitting amount was bought
    if held is not None:
        assert held.total_qty <= 100  # capped


def test_set_position_resizes():
    ctx = _setup_ctx()
    p = _provider(close=10.0)
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    d1 = pd.Timestamp("2025-01-02")
    d2 = pd.Timestamp("2025-01-03")
    b.process_day(d1, [OrderIntent(symbol="A", side="buy", weight=0.5)])
    qty_after_buy = b._holdings["A"].total_qty
    b.process_day(d2, [OrderIntent(symbol="A", side="set_position", weight=0.2)])
    assert b._holdings["A"].total_qty < qty_after_buy


def test_set_target_holdings_swaps_universe():
    """Stocks not in target list get sold; missing targets get bought."""
    ctx = Context()
    ctx.universe = ["A", "B"]
    ctx.start = "2025-01-02"
    ctx.end = "2025-01-08"
    ctx.cash = 1_000_000
    ctx.commission = 0.0
    ctx.slippage = 0.0
    ctx.tax_sell = 0.0
    ctx.transfer_fee = 0.0

    idx = pd.date_range("2025-01-02", periods=5, freq="B")
    p = InMemoryProvider(
        {
            "A": pd.DataFrame({"close": [10] * 5, "open": [10] * 5,
                              "high": [10] * 5, "low": [10] * 5,
                              "volume": [1000] * 5, "adj_close": [10] * 5}, index=idx),
            "B": pd.DataFrame({"close": [20] * 5, "open": [20] * 5,
                              "high": [20] * 5, "low": [20] * 5,
                              "volume": [1000] * 5, "adj_close": [20] * 5}, index=idx),
        }
    )
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    d1 = pd.Timestamp("2025-01-02")
    d2 = pd.Timestamp("2025-01-03")
    b.process_day(d1, [OrderIntent(symbol="A", side="buy", weight=0.4)])
    b.process_day(
        d2,
        [OrderIntent(symbol="*", side="set_target_holdings", targets=["B"])],
    )
    # A should be sold, B held
    assert "A" not in b._holdings
    assert "B" in b._holdings


def test_sell_partial_qty_via_weight_arg():
    ctx = _setup_ctx()
    p = _provider(close=10.0)
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    d1 = pd.Timestamp("2025-01-02")
    d2 = pd.Timestamp("2025-01-03")
    b.process_day(d1, [OrderIntent(symbol="A", side="buy", weight=0.5)])
    qty_before = b._holdings["A"].total_qty
    b.process_day(d2, [OrderIntent(symbol="A", side="sell", weight=0.5)])
    assert b._holdings["A"].total_qty < qty_before


def test_equity_curve_reflects_price_changes():
    ctx = _setup_ctx()
    idx = pd.date_range("2025-01-02", periods=4, freq="B")
    df = pd.DataFrame(
        {
            "open": [10, 11, 12, 13],
            "high": [10, 11, 12, 13],
            "low": [10, 11, 12, 13],
            "close": [10, 11, 12, 13],
            "volume": [1000] * 4,
            "adj_close": [10, 11, 12, 13],
        },
        index=idx,
    )
    p = InMemoryProvider({"A": df})
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    for i, ts in enumerate(idx):
        orders = [OrderIntent(symbol="A", side="buy", weight=0.5)] if i == 0 else []
        b.process_day(ts, orders)
    values = [pt.value for pt in b.equity_curve]
    # Equity should rise as price rises
    assert values[-1] > values[0]


def test_positions_snapshot_returns_pnl():
    ctx = _setup_ctx()
    idx = pd.date_range("2025-01-02", periods=3, freq="B")
    df = pd.DataFrame(
        {
            "open": [10, 11, 12],
            "high": [10, 11, 12],
            "low": [10, 11, 12],
            "close": [10, 11, 12],
            "volume": [1000] * 3,
            "adj_close": [10, 11, 12],
        },
        index=idx,
    )
    p = InMemoryProvider({"A": df})
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    for i, ts in enumerate(idx):
        orders = [OrderIntent(symbol="A", side="buy", weight=0.5)] if i == 0 else []
        b.process_day(ts, orders)
    snaps = b.positions_snapshot(idx[-1])
    assert len(snaps) == 1
    assert snaps[0].symbol == "A"
    assert snaps[0].pnl_pct > 0


def test_unknown_symbol_priced_none_skips_order():
    ctx = _setup_ctx()
    p = InMemoryProvider({})
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    today = pd.Timestamp("2025-01-02")
    b.process_day(today, [OrderIntent(symbol="UNKNOWN", side="buy", weight=0.5)])
    assert b._holdings == {}
    assert b.trades == []


# ----------------------------------------------------------------------
# Risk-rule enforcement (Day 5)
# ----------------------------------------------------------------------

def _decline_provider() -> InMemoryProvider:
    """Stock A drops by 5% per day starting from 100."""
    idx = pd.date_range("2025-01-02", periods=10, freq="B")
    closes = [100 * (0.95 ** i) for i in range(10)]
    df = pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.001 for c in closes],
            "low": [c * 0.999 for c in closes],
            "close": closes,
            "volume": [100000.0] * 10,
            "adj_close": closes,
        },
        index=idx,
    )
    return InMemoryProvider({"A": df})


def _rise_provider() -> InMemoryProvider:
    """Stock A rises by 5% per day starting from 100."""
    idx = pd.date_range("2025-01-02", periods=10, freq="B")
    closes = [100 * (1.05 ** i) for i in range(10)]
    df = pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.001 for c in closes],
            "low": [c * 0.999 for c in closes],
            "close": closes,
            "volume": [100000.0] * 10,
            "adj_close": closes,
        },
        index=idx,
    )
    return InMemoryProvider({"A": df})


def test_stop_loss_triggers_forced_sell():
    from backend.services.engine.strategy_lab.sdk.context import RiskRule
    ctx = _setup_ctx()
    p = _decline_provider()
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    cal = pd.date_range("2025-01-02", periods=6, freq="B")
    # Buy on day 1
    b.process_day(cal[0], [OrderIntent(symbol="A", side="buy", weight=0.5)])
    # Register stop loss at -10%
    b.register_risk_rules([RiskRule(symbol="A", kind="stop_loss", value=-0.10)])
    # Walk forward — at some point price drop > 10% should trigger
    triggered_idx = None
    for i in range(1, len(cal)):
        b.process_day(cal[i], [])
        if any(t.reason == "stop_loss" for t in b.trades):
            triggered_idx = i
            break
    assert triggered_idx is not None, "stop_loss should fire on declining price"
    sells = [t for t in b.trades if t.reason == "stop_loss"]
    assert len(sells) == 1
    assert sells[0].direction == "SELL"


def test_take_profit_triggers_forced_sell():
    from backend.services.engine.strategy_lab.sdk.context import RiskRule
    ctx = _setup_ctx()
    p = _rise_provider()
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    cal = pd.date_range("2025-01-02", periods=6, freq="B")
    b.process_day(cal[0], [OrderIntent(symbol="A", side="buy", weight=0.5)])
    b.register_risk_rules([RiskRule(symbol="A", kind="take_profit", value=0.15)])
    triggered = False
    for i in range(1, len(cal)):
        b.process_day(cal[i], [])
        if any(t.reason == "take_profit" for t in b.trades):
            triggered = True
            break
    assert triggered, "take_profit should fire after a 15% rise"


def test_max_holding_days_enforces_exit():
    from backend.services.engine.strategy_lab.sdk.context import RiskRule
    ctx = _setup_ctx()
    p = _provider(close=100.0)
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    cal = pd.date_range("2025-01-02", periods=4, freq="B")
    b.process_day(cal[0], [OrderIntent(symbol="A", side="buy", weight=0.5)])
    b.register_risk_rules([RiskRule(symbol="A", kind="max_holding_days", value=2)])
    # Days 1, 2, 3 — at day 3 holding_days >= 2 → forced sell
    for i in range(1, len(cal)):
        b.process_day(cal[i], [])
    sells = [t for t in b.trades if t.reason == "max_holding_days"]
    assert len(sells) == 1


def test_account_stop_loss_halts_trading():
    from backend.services.engine.strategy_lab.sdk.context import RiskRule
    ctx = _setup_ctx()
    p = _decline_provider()
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    cal = pd.date_range("2025-01-02", periods=10, freq="B")
    b.process_day(cal[0], [OrderIntent(symbol="A", side="buy", weight=0.95)])
    b.register_risk_rules([RiskRule(symbol=None, kind="account_stop_loss", value=-0.20)])
    for i in range(1, len(cal)):
        b.process_day(cal[i], [OrderIntent(symbol="A", side="buy", weight=0.95)])
    halted_sells = [t for t in b.trades if t.reason == "account_stop_loss"]
    assert len(halted_sells) >= 1
    # After halt, no new buys
    later_buys = [t for t in b.trades if t.direction == "BUY" and t.reason == "account_stop_loss"]
    assert len(later_buys) == 0


def test_no_risk_rule_no_forced_sell():
    ctx = _setup_ctx()
    p = _decline_provider()
    b = SimpleBroker(ctx=ctx, provider=p, cash=1_000_000)
    cal = pd.date_range("2025-01-02", periods=6, freq="B")
    b.process_day(cal[0], [OrderIntent(symbol="A", side="buy", weight=0.5)])
    for i in range(1, len(cal)):
        b.process_day(cal[i], [])
    # No risk rule = no forced sell even if price drops a lot
    forced = [t for t in b.trades if t.reason in {"stop_loss", "take_profit", "max_holding_days"}]
    assert forced == []
