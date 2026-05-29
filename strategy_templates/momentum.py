"""
趋势动量策略 (Momentum Strategy)
[Native] 核心逻辑：基于过去 20-60 天的累计收益率进行排名。
"""
STRATEGY_CONFIG = {
    "class": "RedisTopkStrategy",
    "kwargs": {
        "topk": 30,
        "n_drop": 6,
        "momentum_period": 20
    }
}
