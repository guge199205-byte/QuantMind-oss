"""
止损止盈策略 (Stop-Loss / Take-Profit Strategy)
[Native] 核心逻辑：每日持仓浮亏超过 stop_loss 或浮盈超过 take_profit 时，强制平仓并从选股池剔除。
"""
STRATEGY_CONFIG = {
    "class": "RedisStopLossStrategy",
    "kwargs": {
        "signal": "<PRED>",
        "topk": 30,
        "n_drop": 6,
        "stop_loss": -0.08,
        "take_profit": 0.15,
    }
}
