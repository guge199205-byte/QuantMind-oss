from sqlalchemy import (
    DECIMAL,
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.services.api.models.base import Base


class SubscriptionPlan(Base):
    """Subscription Plan (e.g., Free, Pro, Enterprise)"""

    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="Plan ID")
    name = Column(String(100), nullable=False, comment="Plan Name")
    code = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Plan Code (e.g., pro_monthly)",
    )
    description = Column(String(255), comment="Description")
    price = Column(DECIMAL(10, 2), nullable=False, default=0.00, comment="Price")
    currency = Column(String(3), default="CNY", comment="Currency")
    interval = Column(
        String(20), default="month", comment="Billing Interval (month/year)"
    )
    features = Column(
        JSON, default=[], comment="List of feature codes enabled by this plan"
    )
    is_active = Column(Boolean, default=True, comment="Is Plan Active")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), comment="Created At"
    )
    updated_at = Column(
        DateTime(timezone=True), onupdate=func.now(), comment="Updated At"
    )

    subscriptions = relationship("UserSubscription", back_populates="plan")


class UserSubscription(Base):
    """User Subscription Record"""

    __tablename__ = "user_subscriptions"

    id = Column(
        Integer, primary_key=True, autoincrement=True, comment="Subscription ID"
    )
    user_id = Column(String(64), nullable=False, index=True, comment="User ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="Tenant ID")
    plan_id = Column(
        Integer, ForeignKey("subscription_plans.id"), nullable=False, comment="Plan ID"
    )

    status = Column(
        String(20), default="active", comment="Status (active, expired, cancelled)"
    )
    start_date = Column(DateTime(timezone=True), nullable=False, comment="Start Date")
    end_date = Column(DateTime(timezone=True), nullable=False, comment="End Date")
    auto_renew = Column(Boolean, default=True, comment="Auto Renew")

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), comment="Created At"
    )
    updated_at = Column(
        DateTime(timezone=True), onupdate=func.now(), comment="Updated At"
    )

    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
