import logging
from typing import Any, Dict, List, Optional

from backend.services.engine.qlib_app.schemas.backtest import RebalanceInstruction

logger = logging.getLogger(__name__)


class OrderGenerationService:
    """
    调仓指令生成服务
    负责将回测产生的理想权重转化为可执行的买卖指令
    """

    @staticmethod
    def generate_rebalance_instructions(
        target_positions: list[dict[str, Any]],
        current_holdings: list[dict[str, Any]] | None = None,
        total_assets: float = 1000000.0,
        threshold: float = 0.001,  # 忽略小于 0.1% 的权重变动
    ) -> list[RebalanceInstruction]:
        """
        生成调仓建议
        :param target_positions: 理想持仓列表 [{'symbol': '...', 'weight': ...}]
        :param current_holdings: 实际当前持仓 (如果不传，则视为从空仓开始)
        """
        instructions = []

        # 1. 标准化目标持仓
        targets = {item["symbol"]: item["weight"] for item in target_positions}

        # 2. 标准化当前持仓
        currents = {}
        if current_holdings:
            currents = {item["symbol"]: item.get("weight", 0.0) for item in current_holdings}

        # 3. 合并所有涉及的股票
        all_symbols = set(targets.keys()) | set(currents.keys())

        for symbol in all_symbols:
            tw = targets.get(symbol, 0.0)
            cw = currents.get(symbol, 0.0)
            diff = tw - cw

            if abs(diff) < threshold:
                action = "hold"
            elif diff > 0:
                action = "buy"
            else:
                action = "sell"

            if action != "hold" or (tw > 0 and cw > 0):
                instructions.append(
                    RebalanceInstruction(
                        symbol=symbol,
                        action=action,
                        current_weight=round(cw, 4),
                        target_weight=round(tw, 4),
                        weight_diff=round(diff, 4),
                        estimated_amount=round(diff * total_assets, 2),
                    )
                )

        # 按变动金额排序，卖出在前（释放资金），买入在后
        instructions.sort(key=lambda x: x.weight_diff)

        return instructions
