"""
Risk Service - Risk control business logic
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.trade.models.order import Order
from backend.services.trade.models.risk_rule import RiskRule
from backend.services.trade.redis_client import RedisClient
from backend.services.trade.schemas.risk_rule import RiskRuleCreate, RiskRuleUpdate
from backend.services.trade.trade_config import settings
from backend.shared.margin_stock_pool import get_margin_stock_pool_service

logger = logging.getLogger(__name__)


class RiskService:
    """Risk control service"""

    def __init__(self, db: AsyncSession, redis: RedisClient):
        self.db = db
        self.redis = redis

    @staticmethod
    def _normalize_trade_action_value(value: Any) -> str:
        if value is None:
            return ""
        return str(getattr(value, "value", value) or "").strip().lower()

    @staticmethod
    def _parse_whitelist(raw: str) -> set[str]:
        return {item.strip() for item in str(raw or "").split(",") if item and item.strip()}

    @staticmethod
    def _resolve_board_min_lot(symbol: str) -> tuple[str, int]:
        s = str(symbol or "").strip().upper()
        code = s.split(".", 1)[0]
        if code.startswith("688"):
            return "STAR", max(1, int(getattr(settings, "MIN_LOT_STAR_BOARD", 200)))
        if code.startswith("30"):
            return "GEM", max(1, int(getattr(settings, "MIN_LOT_GEM_BOARD", 100)))
        if s.endswith(".BJ") or code.startswith(("8", "9")):
            return "BJ", max(1, int(getattr(settings, "MIN_LOT_BJ_BOARD", 100)))
        return "MAIN", max(1, int(getattr(settings, "MIN_LOT_MAIN_BOARD", 100)))

    async def _load_trade_account_snapshot(self, tenant_id: str, user_id: int) -> dict[str, Any]:
        try:
            from backend.services.trade.routers.real_trading_utils import _fetch_latest_real_account_snapshot

            snapshot = await _fetch_latest_real_account_snapshot(
                self.db,
                tenant_id=tenant_id,
                user_id=str(user_id),
            )
            if not snapshot:
                return {}
            payload = snapshot.get("payload_json") or {}
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    async def create_rule(self, rule_data: RiskRuleCreate) -> RiskRule:
        """Create a risk rule"""
        rule = RiskRule(
            rule_name=rule_data.rule_name,
            rule_type=rule_data.rule_type,
            description=rule_data.description,
            is_active=rule_data.is_active,
            parameters=rule_data.parameters,
            applies_to_all=rule_data.applies_to_all,
            user_ids=rule_data.user_ids,
            priority=rule_data.priority,
        )

        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)

        logger.info(f"Risk rule created: {rule.rule_name}")

        # Invalidate cache
        self.redis.delete("risk:rules:all")

        return rule

    async def get_rule(self, rule_id: int) -> RiskRule | None:
        """Get risk rule by ID"""
        result = await self.db.execute(select(RiskRule).where(RiskRule.id == rule_id))
        return result.scalar_one_or_none()

    async def get_rule_by_name(self, rule_name: str) -> RiskRule | None:
        """Get risk rule by name"""
        result = await self.db.execute(select(RiskRule).where(RiskRule.rule_name == rule_name))
        return result.scalar_one_or_none()

    async def update_rule(self, rule_id: int, update_data: RiskRuleUpdate) -> RiskRule | None:
        """Update risk rule"""
        rule = await self.get_rule(rule_id)
        if not rule:
            return None

        # Update fields
        if update_data.rule_name is not None:
            rule.rule_name = update_data.rule_name
        if update_data.rule_type is not None:
            rule.rule_type = update_data.rule_type
        if update_data.description is not None:
            rule.description = update_data.description
        if update_data.is_active is not None:
            rule.is_active = update_data.is_active
        if update_data.parameters is not None:
            rule.parameters = update_data.parameters
        if update_data.applies_to_all is not None:
            rule.applies_to_all = update_data.applies_to_all
        if update_data.user_ids is not None:
            rule.user_ids = update_data.user_ids
        if update_data.priority is not None:
            rule.priority = update_data.priority

        await self.db.commit()
        await self.db.refresh(rule)

        logger.info(f"Risk rule updated: {rule_id}")

        # Invalidate cache
        self.redis.delete("risk:rules:all")

        return rule

    async def delete_rule(self, rule_id: int) -> bool:
        """Delete risk rule"""
        rule = await self.get_rule(rule_id)
        if not rule:
            return False

        await self.db.delete(rule)
        await self.db.commit()

        logger.info(f"Risk rule deleted: {rule_id}")

        # Invalidate cache
        self.redis.delete("risk:rules:all")

        return True

    async def list_rules(self, active_only: bool = True) -> list[RiskRule]:
        """List all risk rules"""
        conditions = []
        if active_only:
            conditions.append(RiskRule.is_active)

        stmt = select(RiskRule)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(RiskRule.priority.desc(), RiskRule.id)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_applicable_rules(self, user_id: int) -> list[RiskRule]:
        """Get risk rules applicable to a user"""
        rules = await self.list_rules(active_only=True)

        applicable_rules = []
        for rule in rules:
            if rule.applies_to_all:
                applicable_rules.append(rule)
            elif rule.user_ids and user_id in rule.user_ids:
                applicable_rules.append(rule)

        return applicable_rules

    async def check_order_risk(
        self,
        user_id: int,
        order: Order,
        portfolio_value: float = 0.0,
        available_cash: float = -1.0,
        daily_trade_count: int = 0,
    ) -> dict[str, Any]:
        """Check if order passes risk control"""
        rules = await self.get_applicable_rules(user_id)

        violations = []
        is_margin_trade = bool(getattr(order, "is_margin_trade", False))
        trade_action_value = self._normalize_trade_action_value(getattr(order, "trade_action", None))
        is_sell_to_open = trade_action_value == "sell_to_open"
        trading_mode_value = str(getattr(getattr(order, "trading_mode", None), "value", getattr(order, "trading_mode", "")))
        is_real_mode = trading_mode_value.upper() == "REAL"
        qty = int(float(getattr(order, "quantity", 0) or 0))

        # A 股买入整手校验，科创板默认 200 起步，避免发出交易所直接无效的委托。
        if str(getattr(order.side, "value", "")).lower() == "buy":
            board, min_lot = self._resolve_board_min_lot(getattr(order, "symbol", ""))
            if qty > 0 and qty < min_lot:
                violations.append(
                    {
                        "rule": "min_lot_size",
                        "message": f"{board} board requires min lot {min_lot}, got {qty}",
                    }
                )
            elif qty > 0 and qty % min_lot != 0:
                violations.append(
                    {
                        "rule": "lot_size_multiple",
                        "message": f"{board} board requires lot multiple of {min_lot}, got {qty}",
                    }
                )

        if is_margin_trade and not settings.ENABLE_MARGIN_TRADING:
            violations.append(
                {
                    "rule": "margin_trading_disabled",
                    "message": "Margin trading is disabled by feature flag",
                }
            )

        if is_margin_trade and is_sell_to_open:
            if is_real_mode:
                long_short_enabled = bool(getattr(settings, "ENABLE_LONG_SHORT_REAL", False))
                whitelist_users = self._parse_whitelist(getattr(settings, "LONG_SHORT_WHITELIST_USERS", ""))
                if (not long_short_enabled) or (str(user_id) not in whitelist_users):
                    violations.append(
                        {
                            "rule": "LONG_SHORT_NOT_ENABLED",
                            "message": "LONG_SHORT_NOT_ENABLED: 当前账户未开通实盘多空交易权限",
                        }
                    )

            try:
                pool = get_margin_stock_pool_service(settings.MARGIN_STOCK_POOL_PATH)
                if not pool.is_margin_eligible(order.symbol):
                    violations.append(
                        {
                            "rule": "SHORT_POOL_FORBIDDEN",
                            "message": f"SHORT_POOL_FORBIDDEN: {order.symbol} 不在融资融券股票池中，禁止卖空开仓",
                        }
                    )
            except Exception as exc:
                violations.append(
                    {
                        "rule": "margin_stock_pool_unavailable",
                        "message": f"融资融券股票池不可用: {exc}",
                    }
                )

            margin_required = float(order.order_value or 0.0) * float(settings.MARGIN_SHORT_MARGIN_RATE)
            # A 股融券占用的是担保物额度(总资产)，而非直接消耗可用现金
            # 但为了简化，这里依赖后续的 short_exposure 来控制总敞口
            if portfolio_value > 0 and margin_required > portfolio_value:
                violations.append(
                    {
                        "rule": "margin_requirement",
                        "message": (
                            f"可用担保物不足: required {margin_required:.2f}, " f"portfolio_value {portfolio_value:.2f}"
                        ),
                    }
                )

            if portfolio_value > 0:
                short_exposure = float(order.order_value or 0.0) / portfolio_value
                max_short_exposure = 1.0
                if short_exposure > max_short_exposure:
                    violations.append(
                        {
                            "rule": "max_short_exposure",
                            "message": (f"空头仓位占比 {short_exposure:.1%} 超过最大值 {max_short_exposure:.1%}"),
                        }
                    )

            if bool(getattr(settings, "SHORT_ADMISSION_STRICT", True)) and is_real_mode:
                account_snapshot = await self._load_trade_account_snapshot(order.tenant_id, user_id)
                credit_enabled = bool(account_snapshot.get("credit_enabled", False))
                if not credit_enabled:
                    violations.append(
                        {
                            "rule": "CREDIT_ACCOUNT_UNAVAILABLE",
                            "message": "CREDIT_ACCOUNT_UNAVAILABLE: 信用账户状态不可用或未上报",
                        }
                    )
                shortable_symbols_count = int(account_snapshot.get("shortable_symbols_count") or 0)
                if shortable_symbols_count <= 0:
                    violations.append(
                        {
                            "rule": "SHORT_POOL_FORBIDDEN",
                            "message": "SHORT_POOL_FORBIDDEN: 当前账户融券股票池为空或不可用",
                        }
                    )
                # risk_service 无法直接查询实时单标额度，MVP 阶段要求由 Agent 侧做最终严格拦截。
                # 这里明确给出补偿性校验提示，便于前端与日志定位。
                if account_snapshot and "last_short_check_at" in account_snapshot:
                    pass
                else:
                    violations.append(
                        {
                            "rule": "SHORT_QUOTA_INSUFFICIENT",
                            "message": "SHORT_QUOTA_INSUFFICIENT: 未检测到可用融券额度快照（由Agent最终校验）",
                        }
                    )

        # 1. Purchasing Power Check (Core Mandatory Rule)
        if (
            order.side.value == "buy"
            and available_cash >= 0
            and not (is_margin_trade and trade_action_value == "buy_to_close")
        ):
            # A 股佣金估算：买入约 0.03%，最低 5 元（各券商略有差异）
            # 卖出额外含印花税 0.1% + 过户费 0.001%，此处仅针对 buy 方向做买入佣金估算
            commission_rate = float(getattr(settings, "COMMISSION_RATE_BUY", 0.0003))
            estimated_commission = max(order.order_value * commission_rate, 5.0)
            required_amount = order.order_value + estimated_commission
            if required_amount > available_cash:
                violations.append(
                    {
                        "rule": "purchasing_power",
                        "message": f"Insufficient funds: required {required_amount:.2f}, available {available_cash:.2f}",
                    }
                )

        for rule in rules:
            params = rule.parameters

            if rule.rule_type == "max_order_size":
                max_size = params.get("max_value", settings.MAX_ORDER_SIZE)
                if order.order_value > max_size:
                    violations.append(
                        {
                            "rule": rule.rule_name,
                            "message": f"Order value {order.order_value} exceeds maximum {max_size}",
                        }
                    )

            elif rule.rule_type == "min_order_size":
                min_size = params.get("min_value", settings.MIN_ORDER_SIZE)
                if order.order_value < min_size:
                    violations.append(
                        {
                            "rule": rule.rule_name,
                            "message": f"Order value {order.order_value} below minimum {min_size}",
                        }
                    )

            elif rule.rule_type == "max_position_size":
                max_pct = params.get("max_percentage", settings.MAX_POSITION_SIZE)
                if portfolio_value > 0:
                    position_pct = order.order_value / portfolio_value
                    if position_pct > max_pct:
                        violations.append(
                            {
                                "rule": rule.rule_name,
                                "message": f"Position size {position_pct:.1%} exceeds maximum {max_pct:.1%}",
                            }
                        )

            elif rule.rule_type == "max_daily_trades":
                max_trades = params.get("max_count", settings.MAX_DAILY_TRADES)
                if daily_trade_count >= max_trades:
                    violations.append(
                        {
                            "rule": rule.rule_name,
                            "message": f"Daily trade count {daily_trade_count} reached maximum {max_trades}",
                        }
                    )

        return {"passed": len(violations) == 0, "violations": violations}
