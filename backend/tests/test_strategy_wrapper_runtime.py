import sys
from unittest.mock import MagicMock

import pytest

from backend.services.engine.qlib_app.services.strategy_formatter import StrategyFormatterService


def test_tradedecision_wrapper_runtime_execution():
    formatter = StrategyFormatterService()

    # Strategy that returns a dict (legacy style)
    raw_code = """
import qlib
from qlib.strategy.base import BaseStrategy

class LegacyDictStrategy(BaseStrategy):
    def __init__(self, **kwargs):
        pass
        
    def generate_trade_decision(self, *args, **kwargs):
        # Returns a dict of {stock: amount}
        return {"SH600000": 100.0, "SZ000001": -50.0}
"""
    formatted = formatter.format_and_repair(raw_code)

    # Mock Qlib classes for runtime check
    class MockOrder:
        def __init__(self, stock_id, amount, start_time, end_time, direction):
            self.stock_id = stock_id
            self.amount = amount
            self.start_time = start_time
            self.end_time = end_time
            self.direction = direction

        BUY = 1
        SELL = 0

    class MockTradeDecisionWO:
        def __init__(self, order_list, strategy):
            self.order_list = order_list
            self.strategy = strategy

    # Inject mocks into sys.modules so the wrapper can import them
    mock_decision_mod = MagicMock()
    mock_decision_mod.TradeDecisionWO = MockTradeDecisionWO
    mock_decision_mod.Order = MockOrder
    sys.modules["qlib.backtest.decision"] = mock_decision_mod

    # Also need qlib and qlib.strategy.base
    sys.modules["qlib"] = MagicMock()
    mock_strat_mod = MagicMock()
    mock_strat_mod.BaseStrategy = object
    sys.modules["qlib.strategy.base"] = mock_strat_mod

    # Now execute the formatted code
    namespace = {}
    try:
        exec(formatted, namespace)

        # Instantiate the class
        StrategyClass = namespace["LegacyDictStrategy"]
        strategy = StrategyClass()

        # Call generate_trade_decision
        decision = strategy.generate_trade_decision()

        # Should be a MockTradeDecisionWO
        assert isinstance(decision, MockTradeDecisionWO)
        assert len(decision.order_list) == 2

        # Verify order details
        orders = {o.stock_id: o for o in decision.order_list}
        assert orders["SH600000"].amount == 100.0
        assert orders["SH600000"].direction == MockOrder.BUY
        assert orders["SZ000001"].amount == 50.0  # abs(amount)
        assert orders["SZ000001"].direction == MockOrder.SELL

    finally:
        # Cleanup sys.modules
        del sys.modules["qlib.backtest.decision"]
        del sys.modules["qlib.strategy.base"]
        del sys.modules["qlib"]


if __name__ == "__main__":
    test_tradedecision_wrapper_runtime_execution()
    print("Runtime verification PASSED")
