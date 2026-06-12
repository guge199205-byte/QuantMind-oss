"""Extra branch coverage for Context — provider helpers, runner mutators, edge cases."""

import pandas as pd
import pytest

from backend.services.engine.strategy_lab.sdk.context import Context, StatsView
from backend.services.engine.strategy_lab.sdk.position import Position


# ---- additional config branches ----
def test_benchmark_must_be_string():
    c = Context()
    with pytest.raises(ValueError):
        c.benchmark = ""


def test_max_positions_validation():
    c = Context()
    with pytest.raises(ValueError):
        c.max_positions = 0
    with pytest.raises(ValueError):
        c.max_positions = -3


def test_freq_whitelist():
    c = Context()
    c.freq = "30min"
    with pytest.raises(ValueError):
        c.freq = "1min"


def test_tax_and_transfer_fee_validation():
    c = Context()
    c.tax_sell = 0.0
    c.transfer_fee = 0.0
    with pytest.raises(ValueError):
        c.tax_sell = 0.5
    with pytest.raises(ValueError):
        c.transfer_fee = 1.0


def test_universe_invalid_type():
    c = Context()
    with pytest.raises(TypeError):
        c.universe = 123  # type: ignore[assignment]


def test_universe_list_must_be_strings():
    c = Context()
    with pytest.raises(ValueError):
        c.universe = ["", None]  # type: ignore[list-item]


def test_set_target_holdings_requires_list_or_tuple():
    c = Context()
    with pytest.raises(TypeError):
        c.set_target_holdings("SH600036")  # type: ignore[arg-type]


def test_sell_weight_arg():
    c = Context()
    c.sell("SH600036", weight=0.05, reason="trim")
    o = c._drain_orders()[0]
    assert o.side == "sell"
    assert o.weight == 0.05


def test_set_position_weight_range():
    c = Context()
    with pytest.raises(ValueError):
        c.set_position("x", weight=1.5)


def test_buy_qty_must_be_positive():
    c = Context()
    with pytest.raises(ValueError):
        c.buy("x", qty=0)


# ---- snapshot / benchmark / list_features routing ----
class _SnapProvider:
    def history(self, **_):
        return pd.Series(dtype=float)

    def feature(self, **_):
        return None

    def list_features(self):
        return ["a"]

    def snapshot(self, date, symbols):
        return pd.DataFrame({"close": [1.0]}, index=symbols or ["SH600036"])

    def benchmark_history(self, symbol, n, today):
        return pd.Series([1.0] * n)

    def is_st(self, symbol, today):
        return symbol == "SH900001"

    def is_tradable(self, symbol, today):
        return symbol != "SH900002"

    def industry(self, symbol):
        return "金融"

    def market_cap(self, symbol, today):
        return 1.5e10


def test_snapshot_default_today():
    c = Context()
    c._attach(_SnapProvider(), broker=None, cash=1_000_000)
    c._set_today(pd.Timestamp("2025-06-12"))
    df = c.snapshot()
    assert df.iloc[0]["close"] == 1.0


def test_benchmark_history_routes_through_provider():
    c = Context()
    c._attach(_SnapProvider(), broker=None, cash=1_000_000)
    s = c.benchmark_history(5)
    assert len(s) == 5


def test_provider_helpers():
    c = Context()
    c._attach(_SnapProvider(), broker=None, cash=1_000_000)
    assert c.is_st("SH900001") is True
    assert c.is_tradable("SH900002") is False
    assert c.industry("SH600036") == "金融"
    assert c.market_cap("SH600036") == 1.5e10


def test_provider_helpers_fallback_when_provider_missing_methods():
    class MinimalProvider:
        def history(self, **_): return pd.Series(dtype=float)
        def feature(self, **_): return None
        def list_features(self): return []
        def snapshot(self, **_): return pd.DataFrame()
        def benchmark_history(self, **_): return pd.Series(dtype=float)

    c = Context()
    c._attach(MinimalProvider(), broker=None, cash=1_000_000)
    assert c.is_st("X") is False
    assert c.is_tradable("X") is True
    assert c.industry("X") == ""
    assert c.market_cap("X") is None


# ---- runner-side mutators ----
def test_set_position_runner_removes_when_qty_zero():
    c = Context()
    c._set_position(Position(symbol="A", qty=100, cost=1000, market_value=1100))
    assert c.position("A").qty == 100
    c._set_position(Position(symbol="A", qty=0))
    assert c.position("A").qty == 0
    assert "A" not in c._positions


def test_drain_risk_rules_resets_buffer():
    c = Context()
    c.set_stop_loss("X", -0.10)
    rules = c._drain_risk_rules()
    assert len(rules) == 1
    assert c._drain_risk_rules() == []


def test_attach_sets_cash_and_equity():
    c = Context()
    c._attach(data_provider=None, broker=None, cash=500_000)
    assert c.cash == 500_000
    assert c.equity == 500_000


def test_update_cash_equity():
    c = Context()
    c._attach(data_provider=None, broker=None, cash=500_000)
    c._update_cash_equity(400_000, 510_000)
    assert c.cash == 400_000
    assert c.equity == 510_000


def test_today_property_and_setter():
    c = Context()
    assert c.today is None
    c._set_today(pd.Timestamp("2025-06-12"))
    assert c.today == pd.Timestamp("2025-06-12")


def test_stats_view_default():
    c = Context()
    assert isinstance(c.stats, StatsView)
    assert c.stats.n_trades == 0


def test_set_stop_loss_updates_existing_position():
    c = Context()
    c._set_position(Position(symbol="A", qty=100, cost=1000, market_value=1100))
    c.set_stop_loss("A", -0.08)
    assert c.position("A").stop_loss_pct == -0.08


def test_set_take_profit_updates_existing_position():
    c = Context()
    c._set_position(Position(symbol="A", qty=100, cost=1000, market_value=1100))
    c.set_take_profit("A", 0.20)
    assert c.position("A").take_profit_pct == 0.20


def test_set_max_holding_days_updates_existing_position():
    c = Context()
    c._set_position(Position(symbol="A", qty=100, cost=1000, market_value=1100))
    c.set_max_holding_days("A", 15)
    assert c.position("A").max_holding_days == 15
