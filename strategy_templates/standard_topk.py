"""
默认 Top-K 选股策略 (Standard Top-K Strategy)
[Native] 核心逻辑：Top-K 选股 + 零换手强制约束
"""
STRATEGY_CONFIG = {
    "class": "RedisTopkStrategy",
    "kwargs": {
        "signal": "<PRED>",
        "topk": 50,
        "n_drop": 10,
    }
}
