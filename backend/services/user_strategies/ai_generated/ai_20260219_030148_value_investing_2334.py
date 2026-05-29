from qlib.contrib.strategy.signal_strategy import TopkDropoutStrategy


class MLBasedTopkStrategy(TopkDropoutStrategy):
    """
    ML Enhanced Topk Strategy
    Utilizes pre-trained model signals with dynamic dropout logic.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.min_confidence = kwargs.get("min_confidence", 0.6)

    def STRATEGY_CONFIG(self):
        return {
            "class": "MLBasedTopkStrategy",
            "module_path": "user_strategies.ai_generated.ml_topk",
            "kwargs": {"topk": 30, "n_drop": 3, "signal": "<PRED>"},
        }
