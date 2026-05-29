import hashlib
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import quote_plus

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.services.api.user_app.models.payment import PaymentTransaction
from backend.services.api.user_app.models.subscription import (
    SubscriptionPlan,
    UserSubscription,
)
from backend.services.api.user_app.schemas.subscription import SubscriptionPlanCreate

logger = logging.getLogger(__name__)

ALIPAY_AVAILABLE = False
try:
    from alipay import AliPay

    ALIPAY_AVAILABLE = True
except ImportError:
    logger.warning(
        "python-alipay-sdk not installed. Payment features will be disabled."
    )


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._alipay_client = None

    def _get_alipay_client(self):
        """获取支付宝客户端"""
        if self._alipay_client:
            return self._alipay_client

        if not ALIPAY_AVAILABLE:
            logger.error(
                "python-alipay-sdk not installed. Run: pip install python-alipay-sdk"
            )
            return None

        app_id = os.getenv("ALIPAY_APP_ID")
        private_key = os.getenv("ALIPAY_PRIVATE_KEY")
        alipay_public_key = os.getenv("ALIPAY_PUBLIC_KEY")
        debug = os.getenv("ALIPAY_DEBUG", "false").lower() == "true"

        if not all([app_id, private_key, alipay_public_key]):
            logger.warning("支付宝配置未完整设置")
            return None

        # Helper to format key as PEM with line breaks
        def format_pem(key_str, header):
            if not key_str or key_str.startswith("-----BEGIN"):
                return key_str
            # Remove existing whitespace
            clean_key = "".join(key_str.split())
            # Add line breaks every 64 characters
            lines = [clean_key[i : i + 64] for i in range(0, len(clean_key), 64)]
            body = "\n".join(lines)
            return f"-----BEGIN {header}-----\n{body}\n-----END {header}-----"

        # Ensure keys have PEM headers/footers and correct line breaks
        private_key = format_pem(private_key, "PRIVATE KEY")
        alipay_public_key = format_pem(alipay_public_key, "PUBLIC KEY")

        try:
            self._alipay_client = AliPay(
                appid=app_id,
                app_notify_url=os.getenv("ALIPAY_NOTIFY_URL", ""),
                app_private_key_string=private_key,
                alipay_public_key_string=alipay_public_key,
                sign_type="RSA2",
                debug=debug,
            )
            return self._alipay_client
        except Exception as e:
            logger.error(f"初始化支付宝失败: {e}")
            return None

    async def create_plan(self, plan_data: SubscriptionPlanCreate) -> SubscriptionPlan:
        """Create a new subscription plan"""
        db_plan = SubscriptionPlan(
            name=plan_data.name,
            code=plan_data.code,
            description=plan_data.description,
            price=plan_data.price,
            currency=plan_data.currency,
            interval=plan_data.interval,
            features=plan_data.features,
            is_active=True,
        )
        self.db.add(db_plan)
        await self.db.commit()
        await self.db.refresh(db_plan)
        return db_plan

    async def get_plans(self, active_only: bool = True) -> list[SubscriptionPlan]:
        """List all subscription plans"""
        query = select(SubscriptionPlan)
        if active_only:
            query = query.where(SubscriptionPlan.is_active)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_plan_by_code(self, code: str) -> SubscriptionPlan | None:
        result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.code == code)
        )
        return result.scalars().first()

    async def get_plan_by_id(self, plan_id: int) -> SubscriptionPlan | None:
        """根据ID获取套餐"""
        result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        )
        return result.scalars().first()

    async def create_order(
        self,
        user_id: str,
        tenant_id: str,
        plan_id: int,
    ) -> dict:
        """创建支付订单"""
        plan = await self.get_plan_by_id(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        alipay_client = self._get_alipay_client()
        if not alipay_client:
            raise HTTPException(status_code=500, detail="Payment service not available")

        order_no = f"QM{datetime.now().strftime('%Y%m%d%H%M%S')}{user_id[-4:]}{hashlib.md5(f'{user_id}{plan_id}{datetime.now().timestamp()}'.encode()).hexdigest()[:6].upper()}"

        notify_url = os.getenv(
            "ALIPAY_NOTIFY_URL",
            "http://localhost:8000/api/v1/subscription/alipay-notify",
        )
        return_url = os.getenv(
            "ALIPAY_RETURN_URL", "http://localhost:3000/payment/success"
        )

        try:
            order_string = alipay_client.api_alipay_trade_page_pay(
                out_trade_no=order_no,
                total_amount=str(plan.price),
                subject=f"QuantMind {plan.name}",
                return_url=return_url,
                notify_url=notify_url,
            )
            pay_url = f"https://openapi.alipay.com/gateway.do?{order_string}"
            if os.getenv("ALIPAY_DEBUG", "false").lower() == "true":
                pay_url = f"https://openapi.alipaydev.com/gateway.do?{order_string}"

            # Persistence: save pending transaction
            transaction = PaymentTransaction(
                user_id=user_id,
                tenant_id=tenant_id,
                amount=plan.price,
                currency=plan.currency,
                status="pending",
                provider="alipay",
                transaction_id=order_no,
                description=f"Subscription: {plan.name}",
                metadata_info={"plan_id": plan.id, "plan_code": plan.code},
            )
            self.db.add(transaction)
            await self.db.commit()

            return {
                "orderNo": order_no,
                "planId": plan.id,
                "planName": plan.name,
                "amount": float(plan.price),
                "payUrl": pay_url,
                "status": "pending",
            }
        except Exception as e:
            logger.error(f"创建支付宝订单失败: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create payment order: {str(e)}"
            )

    async def subscribe_user(
        self, user_id: str, tenant_id: str, plan_code: str
    ) -> UserSubscription:
        """Subscribe a user to a plan"""
        plan = await self.get_plan_by_code(plan_code)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # Check for existing active subscription
        existing_query = select(UserSubscription).where(
            UserSubscription.user_id == user_id,
            UserSubscription.status == "active",
            UserSubscription.end_date > datetime.now(),
        )
        existing_result = await self.db.execute(existing_query)
        existing_sub = existing_result.scalars().first()

        start_date = datetime.now()
        if existing_sub:
            # Extend existing subscription or switch plan logic could go here
            # For now, we'll just expire the old one and start a new one (or simple upgrade)
            # Simplification: Cancel old one
            existing_sub.status = "upgraded"
            self.db.add(existing_sub)

        # Calculate end date
        if plan.interval == "month":
            end_date = start_date + timedelta(days=30)
        elif plan.interval == "year":
            end_date = start_date + timedelta(days=365)
        else:
            end_date = start_date + timedelta(days=30)  # Default

        new_sub = UserSubscription(
            user_id=user_id,
            tenant_id=tenant_id,
            plan_id=plan.id,
            status="active",
            start_date=start_date,
            end_date=end_date,
            auto_renew=True,
        )
        self.db.add(new_sub)
        await self.db.commit()
        await self.db.refresh(new_sub)

        # Manually assign plan to avoid lazy load error in Pydantic
        new_sub.plan = plan
        return new_sub

    async def get_user_subscription(self, user_id: str) -> UserSubscription | None:
        """Get current active subscription for a user"""
        query = (
            select(UserSubscription)
            .where(
                UserSubscription.user_id == user_id,
                UserSubscription.status == "active",
                UserSubscription.end_date > datetime.now(),
            )
            .order_by(UserSubscription.end_date.desc())
            .options(selectinload(UserSubscription.plan))
        )

        result = await self.db.execute(query)
        return result.scalars().first()

    async def check_feature_access(self, user_id: str, feature_code: str) -> bool:
        """Check if user has access to a specific feature"""
        sub = await self.get_user_subscription(user_id)
        if not sub:
            return False

        # Eager load plan to access features
        query = (
            select(SubscriptionPlan)
            .join(UserSubscription)
            .where(UserSubscription.id == sub.id)
        )
        result = await self.db.execute(query)
        plan = result.scalars().first()

        if not plan or not plan.features:
            return False

        return feature_code in plan.features

    async def handle_alipay_notify(self, data: dict) -> bool:
        """处理支付宝异步通知"""
        alipay_client = self._get_alipay_client()
        if not alipay_client:
            logger.error("支付宝客户端未就绪，无法处理通知")
            return False

        # 1. 验证签名
        signature = data.pop("sign")
        success = alipay_client.verify(data, signature)
        if not success:
            logger.warning(f"支付宝通知签名验证失败: {data.get('out_trade_no')}")
            return False

        # 2. 检查交易状态
        trade_status = data.get("trade_status")
        if trade_status not in ["TRADE_SUCCESS", "TRADE_FINISHED"]:
            logger.info(
                f"支付宝交易未完成: {data.get('out_trade_no')}, status: {trade_status}"
            )
            return True  # 返回 True 表示处理过了

        # 3. 查找订单
        out_trade_no = data.get("out_trade_no")
        query = select(PaymentTransaction).where(
            PaymentTransaction.transaction_id == out_trade_no
        )
        result = await self.db.execute(query)
        transaction = result.scalars().first()

        if not transaction:
            logger.warning(f"未找到对应的交易记录: {out_trade_no}")
            return False

        if transaction.status == "succeeded":
            logger.info(f"订单已处理过: {out_trade_no}")
            return True

        # 4. 更新订单状态
        transaction.status = "succeeded"
        transaction.completed_at = datetime.now()
        transaction.metadata_info["alipay_trade_no"] = data.get("trade_no")
        self.db.add(transaction)

        # 5. 激活或延长订阅
        plan_code = transaction.metadata_info.get("plan_code")
        if plan_code:
            await self.subscribe_user(
                user_id=transaction.user_id,
                tenant_id=transaction.tenant_id,
                plan_code=plan_code,
            )
            logger.info(f"订阅已激活: {transaction.user_id}, plan: {plan_code}")

        await self.db.commit()
        return True
