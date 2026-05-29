from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class SubscriptionPlanBase(BaseModel):
    name: str
    code: str
    description: str | None = None
    price: Decimal
    currency: str = "CNY"
    interval: str = "month"
    features: list[str] = []


class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass


class SubscriptionPlanResponse(SubscriptionPlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class SubscriptionCreate(BaseModel):
    plan_code: str


class UserSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    plan_id: int
    status: str
    start_date: datetime
    end_date: datetime
    auto_renew: bool
    plan: SubscriptionPlanResponse | None = None  # Include plan details
