"""Tests for Position dataclass."""

from backend.services.engine.strategy_lab.sdk.position import Position


def test_empty_position_is_falsy():
    p = Position(symbol="SH600036")
    assert not p
    assert p.qty == 0
    assert p.pnl == 0.0
    assert p.pnl_pct == 0.0
    assert p.avg_cost == 0.0


def test_pnl_calculations():
    p = Position(symbol="SH600036", qty=100, cost=10000.0, market_value=12000.0, last_price=120.0)
    assert p.pnl == 2000.0
    assert p.pnl_pct == 0.20
    assert p.avg_cost == 100.0
    assert bool(p) is True


def test_to_dict_roundtrip():
    p = Position(
        symbol="SZ000001",
        qty=200,
        cost=20000.0,
        market_value=22000.0,
        last_price=110.0,
        holding_days=5,
        reason="S1_hit",
        detail={"s1": 99.0},
        stop_loss_pct=-0.10,
        take_profit_pct=0.15,
    )
    d = p.to_dict()
    assert d["symbol"] == "SZ000001"
    assert d["qty"] == 200
    assert d["pnl"] == 2000.0
    assert d["pnl_pct"] == 0.10
    assert d["avg_cost"] == 100.0
    assert d["reason"] == "S1_hit"
    assert d["detail"] == {"s1": 99.0}
    assert d["stop_loss_pct"] == -0.10
    assert d["take_profit_pct"] == 0.15


def test_zero_cost_safe():
    p = Position(symbol="SH600036", qty=100, cost=0.0, market_value=100.0)
    assert p.pnl_pct == 0.0
    assert p.avg_cost == 0.0
