from qlib.contrib.strategy.signal_strategy import TopkDropoutStrategy


class DualMAStrategy(TopkDropoutStrategy):
    """
    Dual MA Strategy Demo
    Principle: Buy signals are generated when short MA crosses above long MA.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.short_ma = kwargs.get("short_ma", 5)
        self.long_ma = kwargs.get("long_ma", 20)

    def STRATEGY_CONFIG(self):
        return {
            "class": "DualMAStrategy",
            "module_path": "user_strategies.ai_generated.demo_ma",
            "kwargs": {
                "short_ma": self.short_ma,
                "long_ma": self.long_ma,
                "topk": 30,
                "n_drop": 5,
            },
        }
