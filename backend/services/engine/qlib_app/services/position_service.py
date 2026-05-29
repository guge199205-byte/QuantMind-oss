"""
持仓分析服务

提供持仓与行业配置分析
"""

import logging
from typing import Any, Dict, List

from backend.services.engine.qlib_app.schemas.analysis import (
    PositionAnalysisResponse,
    PositionSummary,
    SectorAllocation,
)
from backend.services.engine.qlib_app.services.backtest_persistence import (
    BacktestPersistence,
)
from backend.shared.market_data.service import get_stock_info
from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

logger = logging.getLogger(__name__)
task_logger = StructuredTaskLogger(logger, "BacktestPositionService")


class BacktestPositionService:
    """回测持仓分析服务（离线，基于已完成的回测结果）"""

    def __init__(self):
        self._persistence = BacktestPersistence()
        task_logger.info("initialized", "BacktestPositionService initialized")

    async def analyze(self, backtest_id: str, user_id: str, tenant_id: str = "default") -> PositionAnalysisResponse:
        try:
            # 1. 获取回测结果
            result = await self._persistence.get_result(backtest_id, tenant_id=tenant_id)
            if not result:
                raise ValueError(f"回测结果不存在: {backtest_id}")

            # 2. 提取持仓信息
            holdings = []

            # 优先使用提取的 positions 字段
            if hasattr(result, "positions") and result.positions:
                holdings = await self._parse_positions(result.positions)

            # 如果为空，尝试从 report 的最后一天推导（如果可能）
            if not holdings and result.config:
                # 这里暂时无法从纯净值曲线推导具体持仓，只能返回空
                # 或者如果 result.config 中有 universe，可以模拟等权（但这不准确）
                pass

            # 3. 计算行业配置
            sector_allocations = self._calculate_sector_allocations(holdings)

            # 4. 计算 HHI (赫芬达尔—赫希曼指数)
            # HHI = sum(weight^2)
            total_weight = sum(h.weight for h in holdings)
            if total_weight > 0:
                # 归一化权重
                normalized_weights = [h.weight / total_weight for h in holdings]
                hhi = sum(w**2 for w in normalized_weights)
            else:
                hhi = 0.0

            return PositionAnalysisResponse(
                top_holdings=holdings[:10],  # 仅返回前10大持仓
                sector_allocations=sector_allocations,
                concentration_hhi=float(hhi),
                holdings_count=len(holdings),
            )
        except Exception as exc:
            task_logger.exception("analyze_failed", "持仓分析失败", backtest_id=backtest_id, tenant_id=tenant_id, error=str(exc))
            raise

    async def _parse_positions(self, raw_positions: list[dict[str, Any]]) -> list[PositionSummary]:
        """解析持仓列表并补充股票信息"""
        holdings = []
        sum(float(p.get("weight", 0)) for p in raw_positions)

        for p in raw_positions:
            symbol = p.get("symbol")
            weight = float(p.get("weight", 0))

            # 获取股票信息
            stock_info = await get_stock_info(symbol)

            holdings.append(
                PositionSummary(
                    symbol=symbol,
                    name=stock_info.get("name", symbol),
                    weight=weight,
                    sector=stock_info.get("industry", "其他"),
                )
            )

        # 按权重降序排序
        holdings.sort(key=lambda x: x.weight, reverse=True)
        return holdings

    def _calculate_sector_allocations(self, holdings: list[PositionSummary]) -> list[SectorAllocation]:
        """计算行业配置"""
        sector_map: dict[str, float] = {}
        total_weight = sum(h.weight for h in holdings)

        if total_weight == 0:
            return []

        for h in holdings:
            sector = h.sector or "其他"
            sector_map[sector] = sector_map.get(sector, 0.0) + h.weight

        allocations = []
        for sector, weight in sector_map.items():
            allocations.append(
                SectorAllocation(
                    sector=sector,
                    weight=weight,  # 绝对权重
                    contribution=weight / total_weight,  # 相对贡献
                )
            )

        # 按权重降序排序
        allocations.sort(key=lambda x: x.weight, reverse=True)
        return allocations


# 向后兼容别名，避免其他模块直接使用 PositionService 时报错
PositionService = BacktestPositionService
