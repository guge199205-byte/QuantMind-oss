import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

logger = logging.getLogger(__name__)
task_logger = StructuredTaskLogger(logger, "FactorAnalysisService")


class FactorAnalysisService:
    """
    因子/信号质量分析服务
    提供 IC, ICIR, 分层收益等深度指标
    """

    @staticmethod
    def calculate_ic_metrics(pred: pd.DataFrame, label: pd.DataFrame) -> dict[str, Any]:
        """
        计算 IC 指标
        :param pred: 预测得分 (datetime, instrument) -> score
        :param label: 真实收益 (datetime, instrument) -> label
        """
        try:
            # 合并数据
            data = pd.concat([pred, label], axis=1).dropna()
            if data.empty:
                return {}

            cols = data.columns
            # 计算每日 Rank IC
            ic_series = data.groupby(level="datetime").apply(lambda x: x[cols[0]].corr(x[cols[1]], method="spearman"))

            metrics = {
                "rank_ic": float(ic_series.mean()),
                "rank_ic_std": float(ic_series.std()),
                "icir": (float(ic_series.mean() / ic_series.std()) if ic_series.std() != 0 else 0.0),
                "ic_decay": [],  # 可扩展：计算滞后 IC
            }

            return metrics
        except Exception as e:
            task_logger.error("calculate_ic_metrics_failed", "IC计算失败", error=str(e))
            return {}

    @staticmethod
    def calculate_stratified_returns(
        pred: pd.DataFrame, label: pd.DataFrame, n_groups: int = 5
    ) -> list[dict[str, Any]]:
        """
        计算分层收益（多空分层）
        """
        try:
            data = pd.concat([pred, label], axis=1).dropna()
            if data.empty:
                return []

            pred_col = data.columns[0]
            label_col = data.columns[1]

            # 向量化计算每日分层
            data["group"] = data.groupby(level="datetime")[pred_col].transform(
                lambda x: pd.qcut(x.rank(method="first"), n_groups, labels=False)
            )
            stratified = data.groupby(["datetime", "group"])[label_col].mean().unstack("group")

            res = []
            for i in range(n_groups):
                if i in stratified.columns:
                    group_data = stratified[i].dropna()
                    res.append(
                        {
                            "group": i + 1,
                            "avg_return": float(group_data.mean()),
                            "total_return": float((group_data + 1).prod() - 1),
                            "volatility": (float(group_data.std() * np.sqrt(252)) if len(group_data) > 1 else 0.0),
                        }
                    )
            return res
        except Exception as e:
            task_logger.error("calculate_stratified_returns_failed", "分层收益计算失败", error=str(e))
            return []
