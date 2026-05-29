import pytest

from backend.services.engine.qlib_app.services.strategy_formatter import StrategyFormatterService


def test_formatter_injects_base_strategy_import():
    formatter = StrategyFormatterService()
    raw_code = "class MyStrategy:\n    pass"
    formatted = formatter.format_and_repair(raw_code)

    assert "from qlib.strategy.base import BaseStrategy" in formatted
    assert "class MyStrategy:" in formatted


def test_formatter_patches_legacy_imports():
    formatter = StrategyFormatterService()
    raw_code = "from qlib.contrib.strategy import BaseStrategy\n\nclass MyStrategy:\n    pass"
    formatted = formatter.format_and_repair(raw_code)

    assert "from qlib.contrib.strategy import BaseStrategy" not in formatted
    assert "from qlib.strategy.base import BaseStrategy" in formatted


def test_formatter_injects_get_strategy_config():
    formatter = StrategyFormatterService()
    raw_code = "class AStrategy(BaseStrategy):\n    def __init__(self):\n        pass"
    formatted = formatter.format_and_repair(raw_code)

    assert "def get_strategy_config():" in formatted
    assert '"class": "AStrategy"' in formatted


def test_formatter_skips_when_config_present():
    formatter = StrategyFormatterService()
    raw_code = "class AStrategy:\n    pass\ndef get_strategy_config():\n    return {}"
    formatted = formatter.format_and_repair(raw_code)

    # Should not inject a second get_strategy_config
    assert formatted.count("def get_strategy_config():") == 1


def test_formatter_parameter_auto_repair():
    formatter = StrategyFormatterService()
    raw_code = """
class ConservativeStrategy(BaseStrategy):
    def __init__(self, pool_file_key, pool_file_url, signal="<PRED>", topk=50):
        pass
"""
    formatted = formatter.format_and_repair(raw_code)

    assert '"pool_file_key": ""' in formatted
    assert '"pool_file_url": ""' in formatted
    # signal and topk have defaults, so they shouldn't be in the auto-injected kwargs
    assert '"signal"' not in formatted
    assert '"topk"' not in formatted


def test_formatter_patches_variety_legacy_imports():
    formatter = StrategyFormatterService()
    raw_code = """
import qlib.contrib.strategy as qcs
from qlib.contrib.strategy.base import BaseStrategy
from qlib.contrib.strategy.signal_strategy import SignalStrategy
"""
    formatted = formatter.format_and_repair(raw_code)

    assert "import qlib.contrib.strategy as qcs" not in formatted
    assert "from qlib.contrib.strategy.base import BaseStrategy" not in formatted
    assert "import qlib.strategy.base as qcs" in formatted
    assert "from qlib.strategy.base import BaseStrategy" in formatted
    assert "from qlib.contrib.strategy.signal_strategy import SignalStrategy" in formatted


def test_formatter_keeps_weight_strategy_base_import():
    formatter = StrategyFormatterService()
    raw_code = """
from qlib.contrib.strategy.signal_strategy import WeightStrategyBase

class MyWeightStrategy(WeightStrategyBase):
    pass
"""
    formatted = formatter.format_and_repair(raw_code)

    assert "from qlib.contrib.strategy.signal_strategy import WeightStrategyBase" in formatted
    assert "from qlib.strategy.base import WeightStrategyBase" not in formatted


def test_formatter_empty_content():
    formatter = StrategyFormatterService()
    assert formatter.format_and_repair("") == ""
    assert formatter.format_and_repair("   ") == "   "


def test_formatter_injects_tradedecision_wrapper():
    formatter = StrategyFormatterService()
    raw_code = """
class MyStrategy(BaseStrategy):
    def generate_trade_decision(self, *args, **kwargs):
        return {"SH600000": 100}
"""
    formatted = formatter.format_and_repair(raw_code)

    assert "TradeDecision Compatibility Wrapper" in formatted
    assert "MyStrategy._original_generate_trade_decision = MyStrategy.generate_trade_decision" in formatted
    assert "MyStrategy.generate_trade_decision = _ensure_trade_decision" in formatted


def test_formatter_robust_placeholders():
    formatter = StrategyFormatterService()
    raw_code = """
class MyStrategy(BaseStrategy):
    def __init__(self, condition, position_config):
        pass
"""
    formatted = formatter.format_and_repair(raw_code)
    # Checks that it uses {} instead of None
    assert '"condition": {}' in formatted
    assert '"position_config": {}' in formatted
