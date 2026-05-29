import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.services.engine.qlib_app.schemas.backtest import QlibBacktestRequest
from backend.services.engine.qlib_app.services.strategy_builder import CustomStrategyBuilder

# Use a clean strategy
content = """
from qlib.strategy.base import BaseStrategy
from qlib.backtest.decision import TradeDecisionWO

class CustomStrategy(BaseStrategy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def generate_trade_decision(self, execute_result=None):
        return TradeDecisionWO([], self)

def get_strategy_instance():
    return CustomStrategy()
"""

builder = CustomStrategyBuilder()
try:
    from types import SimpleNamespace

    request = SimpleNamespace(strategy_content=content, strategy_params=SimpleNamespace())
    res = builder._build_strategy_from_content(content, request=request)
    print("Type returned:", type(res))
    print("Result:", res)
except Exception:
    import traceback

    traceback.print_exc()
