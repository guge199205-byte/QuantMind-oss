"""
深度学习时序预测策略 (Time-Series GRU/LSTM)
[Native] 核心逻辑：原生加载 .pkl 时序信号，支持 TS 格式特征。
"""
STRATEGY_CONFIG = {
    "class": "RedisRecordingStrategy",
    "kwargs": {
        "signal": "<PRED>",
        "topk": 30,
        "n_drop": 6,
    }
}
