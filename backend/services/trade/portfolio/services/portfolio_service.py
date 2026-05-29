"""
Portfolio Service - 投资组合业务逻辑
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.trade.models.enums import PositionSide
from backend.services.trade.portfolio.config import settings
from backend.services.trade.portfolio.models import (
    Portfolio,
    PortfolioSnapshot,
    Position,
)
from backend.services.trade.portfolio.schemas import PortfolioCreate, PortfolioUpdate
from backend.services.trade.portfolio.services.remote_service import remote_service
from backend.services.trade.portfolio.utils import cache, get_cache_key

logger = logging.getLogger(__name__)


class PortfolioService:
    """投资组合服务"""

    @staticmethod
    async def create_portfolio(db: AsyncSession, data: PortfolioCreate) -> Portfolio:
        """创建投资组合"""
        # 检查用户组合数量限制
        stmt = select(func.count(Portfolio.id)).where(
            and_(
                Portfolio.tenant_id == data.tenant_id,
                Portfolio.user_id == data.user_id,
                Portfolio.is_deleted == False,
            )
        )
        result = await db.execute(stmt)
        count = result.scalar()

        if count >= settings.MAX_PORTFOLIOS_PER_USER:
            raise ValueError(f"超过最大组合数量限制: {settings.MAX_PORTFOLIOS_PER_USER}")

            # 创建组合
        portfolio = Portfolio(
            tenant_id=data.tenant_id,
            user_id=data.user_id,
            name=data.name,
            description=data.description,
            initial_capital=data.initial_capital,
            current_capital=data.initial_capital,
            available_cash=data.initial_capital,
            total_value=data.initial_capital,
        )

        db.add(portfolio)
        await db.flush()
        await db.refresh(portfolio)

        logger.info(f"Created portfolio {portfolio.id} for tenant={data.tenant_id}, user={data.user_id}")
        return portfolio

    @staticmethod
    async def get_portfolio(
        db: AsyncSession,
        portfolio_id: int,
        user_id: int | None = None,
        tenant_id: str | None = None,
    ) -> Portfolio | None:
        """查询投资组合"""
        tenant_scope = (tenant_id or "").strip() or "default" if tenant_id is not None else None
        use_cache = tenant_scope is None and user_id is None
        # 先尝试从缓存获取
        cache_key = get_cache_key("portfolio", "default", portfolio_id)
        if use_cache:
            cached = await cache.get(cache_key)
            if cached:
                p = Portfolio(**{k: v for k, v in cached.items() if k != "_sa_instance_state"})
                return p

        # 从数据库查询
        stmt = select(Portfolio).where(and_(Portfolio.id == portfolio_id, Portfolio.is_deleted == False))

        if tenant_scope is not None:
            stmt = stmt.where(Portfolio.tenant_id == tenant_scope)
        if user_id is not None:
            stmt = stmt.where(Portfolio.user_id == user_id)

        result = await db.execute(stmt)
        portfolio = result.scalar_one_or_none()

        # 缓存结果
        if portfolio and use_cache:
            # 移除 SQLAlchemy 内部状态，并将 Decimal 转换为 string 以便 JSON 序列化
            p_dict = {k: v for k, v in portfolio.__dict__.items() if k != "_sa_instance_state"}
            await cache.set(cache_key, p_dict, settings.CACHE_TTL_PORTFOLIO)

        return portfolio

    @staticmethod
    async def list_portfolios(
        db: AsyncSession,
        tenant_id: str,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> list[Portfolio]:
        """查询投资组合列表"""
        stmt = select(Portfolio).where(
            and_(
                Portfolio.tenant_id == tenant_id,
                Portfolio.user_id == user_id,
                Portfolio.is_deleted == False,
            )
        )

        if status:
            stmt = stmt.where(Portfolio.status == status)

        stmt = stmt.order_by(Portfolio.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def update_portfolio(
        db: AsyncSession,
        portfolio_id: int,
        tenant_id: str,
        user_id: int,
        data: PortfolioUpdate,
    ) -> Portfolio:
        """更新投资组合"""
        portfolio = await PortfolioService.get_portfolio(db, portfolio_id, user_id, tenant_id=tenant_id)
        if not portfolio:
            raise ValueError("投资组合不存在")

            # 更新字段
        if data.name is not None:
            portfolio.name = data.name
        if data.description is not None:
            portfolio.description = data.description
        if data.status is not None:
            portfolio.status = data.status

        portfolio.updated_at = datetime.now()

        await db.flush()
        await db.refresh(portfolio)

        # 清除缓存
        cache_key = get_cache_key("portfolio", "default", portfolio_id)
        await cache.delete(cache_key)

        logger.info(f"Updated portfolio {portfolio_id}")
        return portfolio

    @staticmethod
    async def delete_portfolio(db: AsyncSession, portfolio_id: int, tenant_id: str, user_id: int) -> bool:
        """删除投资组合（软删除）"""
        portfolio = await PortfolioService.get_portfolio(db, portfolio_id, user_id, tenant_id=tenant_id)
        if not portfolio:
            raise ValueError("投资组合不存在")

            # 检查是否有持仓
        stmt = select(func.count(Position.id)).where(
            and_(Position.portfolio_id == portfolio_id, Position.status == "holding")
        )
        result = await db.execute(stmt)
        position_count = result.scalar()

        if position_count > 0:
            raise ValueError("组合中还有持仓，无法删除")

            # 软删除
        portfolio.is_deleted = True
        portfolio.status = "closed"
        portfolio.updated_at = datetime.now()

        await db.flush()

        # 清除缓存
        cache_key = get_cache_key("portfolio", "default", portfolio_id)
        await cache.delete(cache_key)

        logger.info(f"Deleted portfolio {portfolio_id}")
        return True

    @staticmethod
    async def calculate_portfolio_metrics(db: AsyncSession, portfolio: Portfolio) -> Portfolio:
        """计算投资组合指标（含夏普比率、波动率、最大回撤）"""
        from backend.services.trade.portfolio.utils.risk_metrics import (
            compute_risk_metrics,
        )

        # 查询所有持仓
        stmt = select(Position).where(and_(Position.portfolio_id == portfolio.id, Position.status == "holding"))
        result = await db.execute(stmt)
        positions = result.scalars().all()

        # 计算持仓总市值
        total_market_value = sum(
            (Decimal(str(pos.market_value)) if pos.side == PositionSide.LONG else -Decimal(str(pos.market_value)))
            for pos in positions
        )

        # 更新组合总市值
        portfolio.total_value = portfolio.available_cash + total_market_value

        # 计算总盈亏
        total_unrealized_pnl = sum(Decimal(str(pos.unrealized_pnl)) for pos in positions)
        total_realized_pnl = sum(Decimal(str(pos.realized_pnl)) for pos in positions)
        portfolio.total_pnl = total_unrealized_pnl + total_realized_pnl

        # === 基于快照历史计算风险指标与当日盈亏 ===
        snap_stmt = (
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.portfolio_id == portfolio.id)
            .order_by(PortfolioSnapshot.snapshot_date.asc())
        )
        snap_result = await db.execute(snap_stmt)
        # 按日期升序排列
        snapshots = snap_result.scalars().all()

        # === 基于快照历史或昨日基准计算当日盈亏与收益率 ===
        if portfolio.yesterday_total_value > 0:
            portfolio.daily_pnl = portfolio.total_value - portfolio.yesterday_total_value
        else:
            # 兼容旧数据逻辑或初次初始化：倒序查找第一个非今日的快照
            today_date = datetime.now().date()
            last_day_snapshot = None
            for snap in reversed(snapshots):
                if snap.snapshot_date.date() < today_date:
                    last_day_snapshot = snap
                    break

            if last_day_snapshot:
                portfolio.daily_pnl = portfolio.total_value - last_day_snapshot.total_value
                # 顺便补齐基准值，优化后续计算性能
                portfolio.yesterday_total_value = last_day_snapshot.total_value
            else:
                # 如果完全没有历史异日快照（如新账户第一天），当日盈亏即为总盈亏
                portfolio.daily_pnl = portfolio.total_pnl

        # 计算当日收益率：优先以昨日收盘值为分母
        denominator = portfolio.yesterday_total_value if portfolio.yesterday_total_value > 0 else portfolio.initial_capital
        if denominator > 0:
            portfolio.daily_return = portfolio.daily_pnl / denominator
        else:
            portfolio.daily_return = Decimal("0")

        # 计算总收益率
        if portfolio.initial_capital > 0:
            portfolio.total_return = portfolio.total_pnl / portfolio.initial_capital

        # 更新持仓权重
        for pos in positions:
            if portfolio.total_value > 0:
                signed_market_value = pos.market_value if pos.side == PositionSide.LONG else -pos.market_value
                pos.weight = signed_market_value / portfolio.total_value
            else:
                pos.weight = Decimal("0")

        # === 计算风险指标 ===
        # 构建含当前值的净值序列以计算最新的风险指标
        all_values = [float(s.total_value) for s in snapshots]
        all_values.append(float(portfolio.total_value))

        if len(all_values) >= 2:
            metrics = compute_risk_metrics(all_values)

            portfolio.sharpe_ratio = metrics.sharpe_ratio
            portfolio.volatility = metrics.volatility
            portfolio.max_drawdown = metrics.max_drawdown
        elif portfolio.initial_capital > 0 and portfolio.total_value > 0:
            # 只有当前值，无法计算历史风险指标，但可以计算即时回撤
            current = float(portfolio.total_value)
            initial = float(portfolio.initial_capital)
            if current < initial:
                portfolio.max_drawdown = round((initial - current) / initial, 4)

        portfolio.updated_at = datetime.now()
        await db.flush()

        return portfolio

    @staticmethod
    async def create_snapshot(
        db: AsyncSession,
        portfolio: Portfolio,
        is_settlement: bool = False,
    ) -> PortfolioSnapshot:
        """创建投资组合快照（含风险指标计算）"""
        from backend.services.trade.portfolio.utils.risk_metrics import (
            compute_risk_metrics,
        )

        # 统计持仓数量
        stmt = select(func.count(Position.id)).where(
            and_(Position.portfolio_id == portfolio.id, Position.status == "holding")
        )
        result = await db.execute(stmt)
        position_count = result.scalar()

        # 计算持仓市值
        stmt = select(func.sum(Position.market_value)).where(
            and_(Position.portfolio_id == portfolio.id, Position.status == "holding")
        )
        result = await db.execute(stmt)
        market_value = result.scalar() or Decimal("0")

        # 基于历史快照计算风险指标
        snap_stmt = (
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.portfolio_id == portfolio.id)
            .order_by(PortfolioSnapshot.snapshot_date.asc())
        )
        snap_result = await db.execute(snap_stmt)
        snapshots = snap_result.scalars().all()

        sharpe_ratio = None
        volatility = None
        max_drawdown = portfolio.max_drawdown

        # 构建含当前值的净值序列
        total_values = [float(s.total_value) for s in snapshots]
        total_values.append(float(portfolio.total_value))

        if len(total_values) >= 2:
            metrics = compute_risk_metrics(total_values)
            sharpe_ratio = metrics.sharpe_ratio
            volatility = metrics.volatility
            max_drawdown = metrics.max_drawdown

        # 创建快照
        snapshot = PortfolioSnapshot(
            portfolio_id=portfolio.id,
            snapshot_date=datetime.now(),
            total_value=portfolio.total_value,
            available_cash=portfolio.available_cash,
            market_value=market_value,
            total_pnl=portfolio.total_pnl,
            total_return=portfolio.total_return,
            daily_pnl=portfolio.daily_pnl,
            daily_return=portfolio.daily_return,
            max_drawdown=max_drawdown or Decimal("0"),
            sharpe_ratio=sharpe_ratio,
            volatility=volatility,
            position_count=position_count,
            is_settlement=is_settlement,
        )

        db.add(snapshot)

        # 如果是结算快照，更新组合的昨日基准值
        if is_settlement:
            portfolio.yesterday_total_value = portfolio.total_value
            logger.info(f"Settlement: Updated yesterday_total_value for portfolio {portfolio.id} to {portfolio.total_value}")

        await db.flush()

        logger.info(f"Created snapshot for portfolio {portfolio.id} (is_settlement={is_settlement})")
        return snapshot

    @staticmethod
    async def bind_strategy(
        db: AsyncSession,
        portfolio_id: int,
        strategy_id: int,
        tenant_id: str,
        user_id: int,
        token: str,
    ) -> Portfolio:
        """绑定策略到组合"""
        portfolio = await PortfolioService.get_portfolio(db, portfolio_id, user_id, tenant_id=tenant_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # 验证策略是否存在
        await remote_service.get_strategy_code(strategy_id, user_id, token)

        portfolio.strategy_id = strategy_id
        portfolio.updated_at = datetime.now()
        await db.flush()
        await db.refresh(portfolio)

        logger.info(f"Bound strategy {strategy_id} to portfolio {portfolio_id}")
        return portfolio

    @staticmethod
    async def start_real_trading(
        db: AsyncSession, portfolio_id: int, tenant_id: str, user_id: int, token: str
    ) -> Portfolio:
        """启动实盘交易"""
        portfolio = await PortfolioService.get_portfolio(db, portfolio_id, user_id, tenant_id=tenant_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        if not portfolio.strategy_id:
            raise HTTPException(status_code=400, detail="No strategy bound to this portfolio")

        if portfolio.run_status == "running":
            raise HTTPException(status_code=400, detail="Real trading is already running")

        # 获取策略代码
        strategy_data = await remote_service.get_strategy_code(portfolio.strategy_id, user_id, token)
        strategy_config = strategy_data.get("config", {})
        code = strategy_config.get("code")
        if not code:
            raise HTTPException(status_code=400, detail="Strategy code not found in strategy config")

        # 调用 Real Trading Service 启动 K8s 部署
        deployment_id = f"user_{user_id}_port_{portfolio_id}"
        await remote_service.start_real_trading(
            user_id=deployment_id,
            strategy_code=code,
            strategy_filename=f"strategy_{portfolio.strategy_id}.py",
        )

        portfolio.real_trading_id = deployment_id
        portfolio.run_status = "running"
        portfolio.updated_at = datetime.now()
        await db.flush()
        await db.refresh(portfolio)

        logger.info(f"Started real trading for portfolio {portfolio_id}, deployment={deployment_id}")
        return portfolio

    @staticmethod
    async def stop_real_trading(db: AsyncSession, portfolio_id: int, tenant_id: str, user_id: int) -> Portfolio:
        """停止实盘交易"""
        portfolio = await PortfolioService.get_portfolio(db, portfolio_id, user_id, tenant_id=tenant_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        if portfolio.run_status != "running" or not portfolio.real_trading_id:
            raise HTTPException(status_code=400, detail="Real trading is not running")

        await remote_service.stop_real_trading(portfolio.real_trading_id)

        portfolio.run_status = "stopped"
        portfolio.updated_at = datetime.now()
        await db.flush()
        await db.refresh(portfolio)

        logger.info(f"Stopped real trading for portfolio {portfolio_id}")
        return portfolio

    @staticmethod
    async def sync_status(db: AsyncSession, portfolio_id: int, tenant_id: str, user_id: int) -> Portfolio:
        """同步实盘运行状态"""
        portfolio = await PortfolioService.get_portfolio(db, portfolio_id, user_id, tenant_id=tenant_id)
        if not portfolio or not portfolio.real_trading_id:
            return portfolio

        status_data = await remote_service.get_real_trading_status(portfolio.real_trading_id)
        k8s_status = status_data.get("status", "unknown")

        if k8s_status == "running":
            portfolio.run_status = "running"
        elif k8s_status == "not_running":
            portfolio.run_status = "stopped"

        portfolio.updated_at = datetime.now()
        await db.flush()
        await db.refresh(portfolio)
        return portfolio
