import asyncio
import logging
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.trade.portfolio.models import Portfolio, Position
from backend.services.trade.redis_client import redis_client
from backend.services.trade.routers.real_trading_utils import _fetch_latest_real_account_snapshot

logger = logging.getLogger("quantmind.trade.audit")


class TradeAuditService:
    """
    实盘交易审计服务：负责监控云端与 QMT Agent 上报持仓的一致性
    """

    async def run_drift_audit(self, db: AsyncSession, user_id: int, tenant_id: str = "default"):
        """
        执行一次账户偏离度审计
        """
        logger.info(f"[Audit] 启动账户审计: User {user_id}")

        # 1. 获取云端持仓 (From PostgreSQL)
        cloud_positions = await self._get_cloud_positions(db, user_id, tenant_id)

        # 2. 获取柜台真实持仓 (From PostgreSQL latest real_account_snapshots payload)
        broker_snapshot = await _fetch_latest_real_account_snapshot(
            db,
            tenant_id=tenant_id,
            user_id=str(user_id),
        )
        if not broker_snapshot:
            logger.warning(f"[Audit] 审计跳过：未找到 User {user_id} 的柜台实时上报快照(Bridge Agent 可能离线)")
            return {"status": "skipped", "reason": "bridge_offline"}

        broker_data = broker_snapshot.get("payload_json") or {}
        broker_positions_raw = broker_data.get("positions", [])
        broker_positions = {}
        if isinstance(broker_positions_raw, list):
            for pos in broker_positions_raw:
                if not isinstance(pos, dict):
                    continue
                symbol = str(pos.get("symbol") or pos.get("ts_code") or pos.get("code") or "").strip()
                if not symbol:
                    continue
                broker_positions[symbol] = pos
        elif isinstance(broker_positions_raw, dict):
            broker_positions = broker_positions_raw

        # 3. 对比分析
        drift_report = []
        all_symbols = set(cloud_positions.keys()) | set(broker_positions.keys())

        is_critical_drift = False

        for symbol in all_symbols:
            cloud_vol = cloud_positions.get(symbol, 0)
            # 兼容不同 Bridge 上报格式
            broker_info = broker_positions.get(symbol, {})
            broker_vol = broker_info.get("volume", 0) if isinstance(broker_info, dict) else broker_info

            diff = abs(cloud_vol - broker_vol)
            if diff != 0:
                drift_report.append({"symbol": symbol, "cloud_vol": cloud_vol, "broker_vol": broker_vol, "diff": diff})
                # 如果偏差超过 10%，标记为严重偏离
                if cloud_vol > 0 and (diff / cloud_vol) > 0.1:
                    is_critical_drift = True
                    logger.error(f"[Audit] !!! 严重持仓偏离 !!! {symbol}: 云端 {cloud_vol} vs 柜台 {broker_vol}")

        # 4. 结果持久化与告警
        audit_result = {
            "user_id": user_id,
            "timestamp": asyncio.get_event_loop().time(),
            "has_drift": len(drift_report) > 0,
            "is_critical": is_critical_drift,
            "drifts": drift_report,
        }

        # 将审计结果存入 Redis 供前端展示
        audit_key = f"trade:audit:last_report:{tenant_id}:{user_id}"
        redis_client.set(audit_key, audit_result, ttl=3600)

        return audit_result

    async def _get_cloud_positions(self, db: AsyncSession, user_id: int, tenant_id: str) -> dict[str, int]:
        """从数据库查询该用户所有组合的汇总持仓"""
        # 查找该用户的所有活跃组合
        stmt = select(Portfolio.id).where(Portfolio.user_id == user_id, Portfolio.tenant_id == tenant_id)
        result = await db.execute(stmt)
        portfolio_ids = result.scalars().all()

        if not portfolio_ids:
            return {}

        # 汇总持仓
        pos_stmt = select(Position.symbol, Position.quantity).where(Position.portfolio_id.in_(portfolio_ids))
        pos_result = await db.execute(pos_stmt)

        positions = {}
        for row in pos_result.all():
            symbol, qty = row
            positions[symbol] = positions.get(symbol, 0) + qty

        return positions


audit_service = TradeAuditService()
