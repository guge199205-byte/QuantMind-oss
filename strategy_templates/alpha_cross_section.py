"""
截面 Alpha 预测策略 (Cross-sectional Alpha)
[Native] 核心逻辑：按模型预测分比例进行权重分配。
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
