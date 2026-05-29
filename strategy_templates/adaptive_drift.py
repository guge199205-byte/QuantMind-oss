"""
自适应动态调仓策略 (Adaptive Concept Drift)
[Native] 核心逻辑：集成 MarketStateService，自动触发动态仓位开关。
"""
STRATEGY_CONFIG = {
    "class": "RedisRecordingStrategy",
    "kwargs": {
        "signal": "<PRED>",
        "topk": 50,
        "n_drop": 10,
        "dynamic_position": True
    }
}
