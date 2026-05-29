import os
import sys
import unittest
from unittest.mock import MagicMock

# Add backend to path
project_root = os.path.join(os.path.dirname(__file__), "../../")
sys.path.append(project_root)

from backend.services.engine.qlib_app.services.backtest_service import (  # noqa: E402
    QlibBacktestService,
)


class TestCustomStrategyLoader(unittest.TestCase):
    def test_load_strategy_instance(self):
        service = QlibBacktestService()

        # Mock validation to avoid AST checks or env var issues in test env
        service._validate_strategy_content = MagicMock()

        strategy_code = """
class MyStrat:
    def __init__(self):
        self.name = "Custom"

def get_strategy_instance():
    return MyStrat()
"""

        strategy = service._build_strategy_from_content(strategy_code)

        self.assertFalse(isinstance(strategy, dict))
        self.assertEqual(strategy.name, "Custom")
        print("Successfully loaded custom strategy instance!")


if __name__ == "__main__":
    unittest.main()
