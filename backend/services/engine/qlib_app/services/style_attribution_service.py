import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from qlib.data import D

from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

logger = logging.getLogger(__name__)
task_logger = StructuredTaskLogger(logger, "StyleAttributionService")


class StyleAttributionService:
    """
    风格归因服务
    分析投资组合在核心风险因子上的暴露度
    """

    # 定义核心风格因子的 Qlib 表达式
    STYLE_FACTORS = {
        "size": "Log($close * $volume)",  # 简化的规模因子 (市值近似)
        "value": "1 / ($close / $prop_net_asset_value)",  # 简化的账面市值比 (需数据支持)
        "momentum": "$close / Ref($close, 20) - 1",  # 20日动量
        "volatility": "Std($close / Ref($close, 1) - 1, 20)",  # 20日波动率
    }

    @classmethod
    async def analyze_portfolio_exposure(
        cls,
        positions: list[dict[str, Any]],
        benchmark: str,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """
        分析持仓的风格暴露
        :param positions: 每日持仓列表 [{'date': '...', 'symbol': '...', 'weight': ...}]
        """
        try:
            if not positions:
                return {}

            pos_df = pd.DataFrame(positions)
            if "date" not in pos_df.columns:
                return {}

            # 1. 提取所有涉及的股票和日期
            all_symbols = pos_df["symbol"].unique().tolist()
            if benchmark not in all_symbols:
                all_symbols.append(benchmark)

            # 2. 从 Qlib 获取风格因子原始数据
            # 注意：这里只选取回测期内的月末或抽样日期以节省性能，或者直接取期末快照
            # 这里我们取回测最后一日的暴露作为代表
            last_date = pos_df["date"].max()

            # 简化版：计算期末截面的风格暴露
            factor_data = D.features(
                all_symbols,
                list(cls.STYLE_FACTORS.values()),
                start_time=last_date,
                end_time=last_date,
            )

            if factor_data is None or factor_data.empty:
                return {}

            # 清理数据：重命名列
            rev_map = {v: k for k, v in cls.STYLE_FACTORS.items()}
            factor_data = factor_data.rename(columns=rev_map)

            # 3. 标准化因子 (Z-Score)
            for col in cls.STYLE_FACTORS.keys():
                if col in factor_data.columns:
                    m = factor_data[col].mean()
                    s = factor_data[col].std()
                    if s != 0:
                        factor_data[col] = (factor_data[col] - m) / s

            # 4. 计算投资组合加权暴露
            last_day_pos = pos_df[pos_df["date"] == last_date]

            # 如果最后一日没拿到数据，尝试前推一日 (处理非交易日快照问题)
            actual_dates = factor_data.index.get_level_values("datetime").unique()
            target_date = last_date
            if pd.Timestamp(last_date) not in actual_dates:
                target_date = actual_dates.max()
                task_logger.debug(
                    "adjust_analysis_date",
                    "调整风格归因分析日期",
                    from_date=last_date,
                    to_date=str(target_date),
                )

            portfolio_exposure = {}

            for factor in cls.STYLE_FACTORS.keys():
                exposure = 0.0
                total_weight = 0.0
                for _, row in last_day_pos.iterrows():
                    symbol = row["symbol"]
                    weight = row.get("weight", 0)
                    if (symbol, target_date) in factor_data.index:
                        val = factor_data.loc[(symbol, target_date), factor]
                        if not np.isnan(val):
                            exposure += val * weight
                            total_weight += weight

                # 归一化权重下的暴露
                portfolio_exposure[factor] = float(exposure / total_weight) if total_weight > 0 else 0.0

            # 5. 计算基准暴露 (Benchmark Exposure)
            benchmark_exposure = {}
            if (benchmark, target_date) in factor_data.index:
                for factor in cls.STYLE_FACTORS.keys():
                    val = factor_data.loc[(benchmark, target_date), factor]
                    benchmark_exposure[factor] = float(val) if not np.isnan(val) else 0.0

            return {
                "date": str(target_date),
                "portfolio": portfolio_exposure,
                "benchmark": benchmark_exposure,
                "active": {k: portfolio_exposure[k] - benchmark_exposure.get(k, 0) for k in portfolio_exposure},
            }

        except Exception as e:
            task_logger.error("analyze_portfolio_exposure_failed", "风格归因分析失败", error=str(e))
            return {}
