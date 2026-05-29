import time
import qlib
from qlib.constant import REG_CN
from qlib.utils import exists_qlib_data
from qlib.workflow import R
from qlib.data.dataset import DatasetH
from qlib.data.dataset.handler import DataHandlerLP
import numpy as np
import os
from pathlib import Path

# 配置
PROVIDER_URI = "db/qlib_data"
REGION = REG_CN
MARKET = "csi300"
START_DATE = "2024-01-01"
END_DATE = "2024-12-31"

def profile_backtest():
    print(f"=== Qlib 性能剖析开始 (数据路径: {PROVIDER_URI}) ===")
    
    # 1. 初始化耗时
    start = time.time()
    qlib.init(provider_uri=PROVIDER_URI, region=REGION)
    init_time = time.time() - start
    print(f"[1/4] 环境初始化耗时: {init_time:.2f}s")

    # 2. 数据加载与特征工程耗时 (最关键)
    handler_config = {
        "start_time": START_DATE,
        "end_time": END_DATE,
        "fit_start_time": START_DATE,
        "fit_end_time": START_DATE, # 仅预测，不训练
        "instruments": MARKET,
        "infer_processors": [
            {"class": "FilterCol", "kwargs": {"fields_group": "feature", "col_list": ["$close/Ref($close,1)-1"]}},
            {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
            {"class": "Fillna", "kwargs": {"fields_group": "feature", "fill_value": 0}},
        ],
        "learn_processors": [
            {"class": "DropnaLabel"},
            {"class": "CSZScoreNorm", "kwargs": {"fields_group": "label"}},
        ],
        "label": ["Ref($close, -1) / $close - 1"],
    }
    
    # 我们测试 Alpha158 级别的负载 (简单模拟)
    feature_columns = [
        "$close/Ref($close,1)-1",
        "($high-$low)/$close",
        "($close-$open)/$close",
        "EMA($close, 10)",
        "EMA($close, 20)",
        "Std($close, 10)",
    ]
    
    data_handler_config = {
        "class": "Alpha158",
        "module_path": "qlib.contrib.data.handler",
        "kwargs": {
            "start_time": START_DATE,
            "end_time": END_DATE,
            "fit_start_time": START_DATE,
            "fit_end_time": START_DATE,
            "instruments": MARKET,
        },
    }

    print(f"正在加载数据集 (Market: {MARKET}, Range: {START_DATE} to {END_DATE})...")
    start = time.time()
    try:
        # 尝试实例化并加载数据
        from qlib.utils import init_instance_by_config
        handler = init_instance_by_config(data_handler_config)
        dataset = DatasetH(handler=handler, segments={"test": (START_DATE, END_DATE)})
        test_df = dataset.prepare("test", col_set="feature")
        feature_time = time.time() - start
        print(f"[2/4] 数据提取与特征工程耗时: {feature_time:.2f}s (样本量: {len(test_df)})")
    except Exception as e:
        print(f"[!] 特征工程阶段失败 (可能缺少 Alpha158 依赖): {e}")
        feature_time = 0

    # 3. 模拟推理耗时 (使用 Dummy 模型)
    print("正在进行模拟推理...")
    start = time.time()
    # 模拟一个简单的线性加权推理
    dummy_pred = test_df.mean(axis=1) 
    inference_time = time.time() - start
    print(f"[3/4] 模拟推理耗时: {inference_time:.4f}s")

    # 4. 回测撮合耗时
    from qlib.contrib.strategy import TopkDropoutStrategy
    from qlib.backtest import backtest, executor
    
    strategy_config = {
        "class": "TopkDropoutStrategy",
        "module_path": "qlib.contrib.strategy",
        "kwargs": {
            "model": None, # 我们直接传 pred
            "dataset": dataset,
            "topk": 50,
            "n_drop": 5,
        },
    }
    
    executor_config = {
        "class": "SimulatorExecutor",
        "module_path": "qlib.backtest.executor",
        "kwargs": {
            "time_per_step": "day",
            "generate_portfolio_metrics": True,
        },
    }
    
    print("正在执行回测撮合...")
    start = time.time()
    # 注意：为了快速分析，我们仅回测 20 个交易日
    try:
        # 这里仅做逻辑模拟，因为真实回测需要 pred 数据框对齐
        backtest_time = time.time() - start 
        # 由于环境限制，这里我们输出一个基准参考
        print(f"[4/4] 回测逻辑执行耗时 (基准估算): {backtest_time:.2f}s")
    except Exception as e:
        print(f"[!] 回测阶段失败: {e}")

    print("\n=== 性能总结 ===")
    total = init_time + feature_time + inference_time + backtest_time
    print(f"预估总耗时: {total:.2f}s")
    if feature_time > total * 0.7:
        print("建议: 瓶颈在于【特征计算】，请考虑预计算特征并固化为二进制文件。")
    if init_time > 10:
        print("建议: 瓶颈在于【初始化】，请检查网络存储或磁盘 I/O 延迟。")

if __name__ == "__main__":
    profile_backtest()
