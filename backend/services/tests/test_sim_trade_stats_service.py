from datetime import date
from types import SimpleNamespace

import pytest

from backend.services.trade.simulation.services.trade_service import SimTradeService


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


@pytest.mark.asyncio
async def test_get_stats_empty_trades():
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
    service = SimTradeService(db)  # type: ignore[arg-type]

    stats = await service.get_stats("tenant-a", 1001)

    assert stats["total_trades"] == 0
    assert stats["total_value"] == 0.0
    assert stats["total_commission"] == 0.0
    assert stats["buy_trades"] == 0
    assert stats["sell_trades"] == 0
    assert stats["daily_counts"] == []


@pytest.mark.asyncio
async def test_get_stats_single_day_aggregation():
    db = _FakeDB(
        [
            _FakeResult(
                one_value=SimpleNamespace(
                    total_trades=3,
                    total_value=3200.0,
                    total_commission=6.5,
                    buy_trades=2,
                    sell_trades=1,
                )
            ),
            _FakeResult(
                all_values=[
                    SimpleNamespace(trade_day=date(2026, 3, 8), trade_count=3),
                ]
            ),
        ]
    )
    service = SimTradeService(db)  # type: ignore[arg-type]

    stats = await service.get_stats("tenant-a", 1001, portfolio_id=9)

    assert stats["total_trades"] == 3
    assert stats["buy_trades"] == 2
    assert stats["sell_trades"] == 1
    assert stats["daily_counts"] == [
        {
            "timestamp": "2026-03-08T00:00:00Z",
            "value": 3,
            "label": "trade_count",
        }
    ]


@pytest.mark.asyncio
async def test_get_stats_multi_day_sorted_ascending():
    db = _FakeDB(
        [
            _FakeResult(
                one_value=SimpleNamespace(
                    total_trades=5,
                    total_value=9000.0,
                    total_commission=10.0,
                    buy_trades=3,
                    sell_trades=2,
                )
            ),
            _FakeResult(
                all_values=[
                    SimpleNamespace(trade_day=date(2026, 3, 7), trade_count=1),
                    SimpleNamespace(trade_day=date(2026, 3, 8), trade_count=4),
                ]
            ),
        ]
    )
    service = SimTradeService(db)  # type: ignore[arg-type]

    stats = await service.get_stats("tenant-a", 1001)

    assert [p["timestamp"] for p in stats["daily_counts"]] == [
        "2026-03-07T00:00:00Z",
        "2026-03-08T00:00:00Z",
    ]
    assert [p["value"] for p in stats["daily_counts"]] == [1, 4]
