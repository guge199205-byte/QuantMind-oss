import os
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

project_root = os.path.join(os.path.dirname(__file__), "../../")
sys.path.append(project_root)

from backend.services.engine.qlib_app.utils.cn_exchange import CnExchange
from qlib.backtest.decision import OrderDir


class DummyQuote:
    def __init__(self, mapping):
        self.mapping = mapping

    def get_data(self, stock_id, start_time, end_time, field, method="ts_data_last"):
        key = (stock_id, pd.Timestamp(start_time).strftime("%Y-%m-%d"), field)
        return self.mapping.get(key)

    def get_all_stock(self):
        return {"SH600000"}


def make_exchange(mapping):
    exchange = CnExchange.__new__(CnExchange)
    exchange.quote = DummyQuote(mapping)
    exchange.buy_price = "$close"
    exchange.sell_price = "$close"
    exchange.quote_fallback_lookback_days = 3
    exchange.backtest_id = "test"
    return exchange


def test_get_close_falls_back_to_previous_valid_quote():
    exchange = make_exchange(
        {
            ("SH600000", "2026-03-25", "$close"): 0.0,
            ("SH600000", "2026-03-24", "$close"): 12.34,
        }
    )

    price = exchange.get_close("SH600000", pd.Timestamp("2026-03-25"), pd.Timestamp("2026-03-25"))

    assert price == pytest.approx(12.34)


def test_get_factor_falls_back_to_previous_valid_quote():
    exchange = make_exchange(
        {
            ("SH600000", "2026-03-25", "$factor"): 0.0,
            ("SH600000", "2026-03-24", "$factor"): 0.256,
        }
    )

    factor = exchange.get_factor("SH600000", pd.Timestamp("2026-03-25"), pd.Timestamp("2026-03-25"))

    assert factor == pytest.approx(0.256)


def test_get_deal_price_falls_back_to_recent_valid_close():
    exchange = make_exchange(
        {
            ("SH600000", "2026-03-25", "$close"): 0.0,
            ("SH600000", "2026-03-24", "$close"): 8.88,
        }
    )

    price = exchange.get_deal_price(
        "SH600000",
        pd.Timestamp("2026-03-25"),
        pd.Timestamp("2026-03-25"),
        OrderDir.BUY,
    )

    assert price == pytest.approx(8.88)
