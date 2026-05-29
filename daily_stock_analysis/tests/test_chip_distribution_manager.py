# -*- coding: utf-8 -*-
"""Regression tests for chip distribution provider fallback."""

from types import SimpleNamespace
from unittest.mock import patch

from data_provider.base import DataFetcherManager
from data_provider.realtime_types import ChipDistribution, get_chip_circuit_breaker


class _ChipFetcher:
    def __init__(self, name: str, priority: int, result):
        self.name = name
        self.priority = priority
        self._result = result
        self.calls = 0

    def get_chip_distribution(self, stock_code: str):
        self.calls += 1
        return self._result


def test_manager_skips_placeholder_chip_distribution_and_tries_next_fetcher():
    get_chip_circuit_breaker().reset()
    empty_chip = ChipDistribution(code="600519")
    valid_chip = ChipDistribution(
        code="600519",
        profit_ratio=0.61,
        avg_cost=12.3,
        concentration_90=0.13,
    )
    manager = DataFetcherManager(
        fetchers=[
            _ChipFetcher("EmptyFetcher", 0, empty_chip),
            _ChipFetcher("ValidFetcher", 1, valid_chip),
        ]
    )

    with patch("src.config.get_config", return_value=SimpleNamespace(enable_chip_distribution=True)):
        chip = manager.get_chip_distribution("600519")

    assert chip is valid_chip


def test_manager_accepts_zero_concentration_chip_distribution():
    get_chip_circuit_breaker().reset()
    zero_concentration_chip = ChipDistribution(
        code="600519",
        profit_ratio=0.61,
        avg_cost=12.3,
        concentration_90=0.0,
        concentration_70=0.0,
    )
    fallback_chip = ChipDistribution(
        code="600519",
        profit_ratio=0.62,
        avg_cost=12.5,
        concentration_90=0.13,
    )
    zero_fetcher = _ChipFetcher("ZeroConcentrationFetcher", 0, zero_concentration_chip)
    fallback_fetcher = _ChipFetcher("FallbackFetcher", 1, fallback_chip)
    manager = DataFetcherManager(fetchers=[zero_fetcher, fallback_fetcher])

    with patch("src.config.get_config", return_value=SimpleNamespace(enable_chip_distribution=True)):
        chip = manager.get_chip_distribution("600519")

    assert chip is zero_concentration_chip
    assert zero_fetcher.calls == 1
    assert fallback_fetcher.calls == 0
