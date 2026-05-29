"""
绩效归因服务 (Performance Attribution)

提供：
- 持仓贡献度分析
- 行业/板块归因
- 收益分解（选股 vs 配置）
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.trade.portfolio.models import Portfolio, Position

logger = logging.getLogger(__name__)

# A股行业分类映射（简化版，按代码前缀）
SECTOR_MAP = {
    "600": "上证主板",
    "601": "上证主板",
    "603": "上证主板",
    "000": "深证主板",
    "001": "深证主板",
    "002": "中小板",
    "300": "创业板",
    "301": "创业板",
    "688": "科创板",
    "689": "科创板",
}


def _get_sector(symbol: str) -> str:
    """根据股票代码推断板块"""
    code = symbol.split(".")[0]
    for prefix, sector in SECTOR_MAP.items():
        if code.startswith(prefix):
            return sector
    return "其他"


@dataclass
class PositionContribution:
    """单个持仓的贡献度"""

    symbol: str
    symbol_name: str
    weight: float
    pnl: float
    contribution: float  # 对组合收益率的贡献 (pnl / initial_capital)
    contribution_pct: float  # 占总收益的百分比


@dataclass
class SectorAttribution:
    """行业归因"""

    sector: str
    weight: float  # 配置权重
    pnl: float  # 该行业总盈亏
    contribution: float  # 对组合收益率的贡献
    position_count: int  # 持仓数量


@dataclass
class AttributionResult:
    """归因分析完整结果"""

    portfolio_id: int
    analysis_date: str
    total_return: float
    total_pnl: float

    # 持仓贡献度（按贡献排序）
    position_contributions: list[PositionContribution] = field(default_factory=list)
    # 行业归因
    sector_attributions: list[SectorAttribution] = field(default_factory=list)
    # 收益分解
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    commission_cost: float = 0.0

    # Top/Bottom 贡献者
    top_contributors: list[PositionContribution] = field(default_factory=list)
    bottom_contributors: list[PositionContribution] = field(default_factory=list)


class AttributionService:
    """绩效归因分析服务"""

    @staticmethod
    async def analyze(db: AsyncSession, portfolio: Portfolio) -> AttributionResult:
        """对投资组合执行完整归因分析"""

        initial_capital = float(portfolio.initial_capital) or 1.0

        # 查询所有持仓（含已平仓）
        stmt = select(Position).where(Position.portfolio_id == portfolio.id)
        result = await db.execute(stmt)
        positions = result.scalars().all()

        # === 1. 持仓贡献度 ===
        contributions: list[PositionContribution] = []
        total_pnl = 0.0

        for pos in positions:
            pnl = float(pos.unrealized_pnl or 0) + float(pos.realized_pnl or 0)
            total_pnl += pnl
            contrib = pnl / initial_capital if initial_capital > 0 else 0.0

            contributions.append(
                PositionContribution(
                    symbol=pos.symbol,
                    symbol_name=pos.symbol_name or pos.symbol,
                    weight=float(pos.weight or 0),
                    pnl=round(pnl, 2),
                    contribution=round(contrib, 6),
                    contribution_pct=0.0,  # 后面计算
                )
            )

        # 计算贡献占比
        if total_pnl != 0:
            for c in contributions:
                c.contribution_pct = round(c.pnl / abs(total_pnl) * 100, 2)

        # 按贡献度排序
        contributions.sort(key=lambda x: x.pnl, reverse=True)

        # === 2. 行业归因 ===
        sector_map: dict[str, SectorAttribution] = {}
        total_value = float(portfolio.total_value) or 1.0

        for pos in positions:
            if pos.status == "closed" and float(pos.market_value or 0) == 0:
                sector = _get_sector(pos.symbol)
                pnl = float(pos.realized_pnl or 0)
            else:
                sector = _get_sector(pos.symbol)
                pnl = float(pos.unrealized_pnl or 0) + float(pos.realized_pnl or 0)

            if sector not in sector_map:
                sector_map[sector] = SectorAttribution(
                    sector=sector,
                    weight=0.0,
                    pnl=0.0,
                    contribution=0.0,
                    position_count=0,
                )

            sa = sector_map[sector]
            sa.pnl += pnl
            sa.weight += float(pos.market_value or 0) / total_value
            sa.position_count += 1

        for sa in sector_map.values():
            sa.pnl = round(sa.pnl, 2)
            sa.weight = round(sa.weight, 4)
            sa.contribution = round(sa.pnl / initial_capital, 6) if initial_capital > 0 else 0.0

        sector_list = sorted(sector_map.values(), key=lambda x: x.pnl, reverse=True)

        # === 3. 收益分解 ===
        realized = sum(float(p.realized_pnl or 0) for p in positions)
        unrealized = sum(float(p.unrealized_pnl or 0) for p in positions)

        # === 4. Top/Bottom ===
        top5 = contributions[:5] if len(contributions) >= 5 else contributions
        bottom5 = contributions[-5:] if len(contributions) >= 5 else []

        return AttributionResult(
            portfolio_id=portfolio.id,
            analysis_date=datetime.now().isoformat(),
            total_return=float(portfolio.total_return or 0),
            total_pnl=round(total_pnl, 2),
            position_contributions=contributions,
            sector_attributions=sector_list,
            realized_pnl=round(realized, 2),
            unrealized_pnl=round(unrealized, 2),
            top_contributors=top5,
            bottom_contributors=bottom5,
        )
