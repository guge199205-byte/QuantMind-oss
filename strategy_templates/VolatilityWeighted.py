"""
波动率加权 TopK 策略 (Volatility-Weighted Top-K)
[Native] 核心逻辑：Top-K 选股 + 以近期实现波动率的倒数为权重分配仓位。
低波动标的获得更高权重，高波动标的自动降权，降低组合整体风险。
"""
STRATEGY_CONFIG = {
    "class": "RedisVolatilityWeightedStrategy",
    "kwargs": {
        "signal": "<PRED>",
        "topk": 50,
        "vol_lookback": 20,
        "max_weight": 0.10,
        "min_score": 0.0,
    }
}
