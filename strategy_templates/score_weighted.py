"""
得分加权组合策略 (Score-Weighted)
[Native] 核心逻辑：权重 = Score / Sum(Scores)，且 Weight <= Max_Weight。
"""
STRATEGY_CONFIG = {
    "class": "RedisWeightStrategy",
    "kwargs": {
        "signal": "<PRED>",
        "topk": 50,
        "min_score": 0.0,
        "max_weight": 0.05,
    }
}
