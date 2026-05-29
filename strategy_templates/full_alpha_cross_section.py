"""
全量截面 Alpha 预测策略 (Full Cross-sectional Alpha)
[Native] 核心逻辑：每日全量重构 TopK，跌出即卖，涨停/停牌自动顺延补位。
"""
STRATEGY_CONFIG = {
    "class": "RedisFullAlphaStrategy",
    "kwargs": {
        "signal": "<PRED>",
        "topk": 50,
        "max_weight": 0.05,
        "rebalance_days": 1,
    },
}

