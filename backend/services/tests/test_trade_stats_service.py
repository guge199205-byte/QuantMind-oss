from datetime import date
from types import SimpleNamespace

import pytest

from backend.services.trade.services.trade_service import TradeService


class _FakeResult:
    def __init__(self, one_value=None, all_values=None):
        self._one_value = one_value
        self._all_values = all_values or []

    def one(self):
        return self._one_value

    def all(self):
        return self._all_values


class _FakeDB:
    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _stmt):
        if not self._results:
            raise AssertionError("unexpected execute call")
        return self._results.pop(0)


class _FakeRedis:
    pass


@pytest.mark.asyncio
async def test_get_trade_statistics_empty():
    db = _FakeDB(
        [
            _FakeResult(
                one_value=SimpleNamespace(
                    total_trades=0,
                    total_value=0.0,
                    total_commission=0.0,
                    buy_trades=0,
                    sell_trades=0,
                )
            ),
            _FakeResult(all_values=[]),
        ]
    )
    service = TradeService(db, _FakeRedis())  # type: ignore[arg-type]

    stats = await service.get_trade_statistics("default", 1)

    assert stats["daily_counts"] == []
    assert stats["total_trades"] == 0
    assert stats["buy_trades"] == 0
    assert stats["sell_trades"] == 0


@pytest.mark.asyncio
async def test_get_trade_statistics_daily_counts_sorted():
    db = _FakeDB(
        [
            _FakeResult(
                one_value=SimpleNamespace(
                    total_trades=6,
                    total_value=10000.0,
                    total_commission=11.0,
                    buy_trades=4,
                    sell_trades=2,
                )
            ),
            _FakeResult(
                all_values=[
                    SimpleNamespace(trade_day=date(2026, 3, 6), trade_count=2),
                    SimpleNamespace(trade_day=date(2026, 3, 7), trade_count=4),
                ]
            ),
        ]
    )
    service = TradeService(db, _FakeRedis())  # type: ignore[arg-type]

    stats = await service.get_trade_statistics("default", 1, portfolio_id=3)

    assert stats["total_trades"] == 6
    assert stats["total_value"] == 10000.0
    assert stats["total_commission"] == 11.0
    assert stats["buy_trades"] == 4
    assert stats["sell_trades"] == 2
    assert stats["daily_counts"] == [
        {"timestamp": "2026-03-06T00:00:00Z", "value": 2, "label": "trade_count"},
        {"timestamp": "2026-03-07T00:00:00Z", "value": 4, "label": "trade_count"},
    ]
