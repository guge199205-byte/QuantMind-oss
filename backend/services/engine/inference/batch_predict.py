#!/usr/bin/env python3
"""
QuantMind 全市场批量推理工具
---------------------------
功能：读取 Qlib 最新数据，调用生产模型生成全市场预测分。
用途：每日增量入库完成后，生成次日交易参考。
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import qlib

# 路径配置
PROJECT_ROOT = Path(__file__).resolve().parents[4]
MODELS_DIR = PROJECT_ROOT / "models" / "production" / "model_qlib"
OUTPUT_DIR = PROJECT_ROOT / "data" / "predictions"

# 导入内部模块
sys.path.append(str(PROJECT_ROOT))
from backend.services.engine.inference.model_loader import ModelLoader

# 日志配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("BatchPredict")


def run_batch_inference(model_id="model_qlib", target_date=None):
    """
    执行批量推理
    :param model_id: 模型目录名
    :param target_date: 推理日期，默认为 Qlib 日历最后一天
    """
    # 1. 初始化 Qlib
    provider_uri = str(PROJECT_ROOT / "db" / "qlib_data")
    qlib.init(provider_uri=provider_uri, region="cn")

    # 2. 确定日期
    if target_date is None:
        from qlib.data import D

        target_date = D.calendar()[-1]

    logger.info(f"开始推理任务 - 日期: {target_date}, 模型: {model_id}")

    # 3. 加载模型
    loader = ModelLoader(PROJECT_ROOT / "models" / "production")
    loader.load_model(model_id)
    model = loader.get_model(model_id)
    metadata = loader.get_model_metadata(model_id)

    if not model or not metadata:
        logger.error("模型加载失败")
        return

    # 4. 获取特征
    # 注意：这里的特征列名必须与模型训练时一致
    feature_cols = metadata.get("feature_columns", [])
    if not feature_cols:
        logger.error("模型元数据中未发现特征列定义")
        return

    from qlib.data import D

    instruments = D.instruments(market="all")

    # 构建特征获取表达式
    # 假设 CSV 里的列名可以直接映射为 $col
    expressions = [f"${col}" if not col.startswith("$") else col for col in feature_cols]

    logger.info(f"正在从二进制文件读取 {len(instruments)} 只股票的特征...")
    df = D.features(instruments, expressions, start_time=target_date, end_date=target_date)

    if df.empty:
        logger.error(f"在 {target_date} 未找到任何特征数据，请检查入库是否成功")
        return

    # 5. 模型推理
    logger.info(f"执行模型预测 (输入形状: {df.shape})...")
    # 清理索引以便输入模型 (LightGBM 通常接受 values)
    X = df.values
    # 处理可能的 NaN (模型通常不能接受 NaN)
    X = np.nan_to_num(X, nan=0.0)

    scores = model.predict(X)

    # 6. 整理结果
    result_df = pd.DataFrame({"score": scores}, index=df.index)

    # 重置索引，提取 symbol
    result_df = result_df.reset_index()
    result_df.rename(columns={"instrument": "symbol", "datetime": "date"}, inplace=True)

    # 7. 持久化
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"pred_{target_date.strftime('%Y%m%d')}.csv"
    output_path = OUTPUT_DIR / file_name

    result_df.to_csv(output_path, index=False)

    # 同时生成一个“最新”快捷方式
    latest_path = OUTPUT_DIR / "latest_prediction.csv"
    result_df.to_csv(latest_path, index=False)

    logger.info(f"推理完成！结果已保存至: {output_path}")
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="model_qlib")
    parser.add_argument("--date", type=str, default=None)
    args = parser.parse_args()

    target_dt = pd.to_datetime(args.date) if args.date else None
    run_batch_inference(args.model, target_dt)
