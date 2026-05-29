from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.user_app.database import get_db
from backend.services.api.user_app.middleware.auth import (
    get_current_user,
    require_admin,
)
from backend.services.api.user_app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionPlanCreate,
    SubscriptionPlanResponse,
    UserSubscriptionResponse,
)
from backend.services.api.user_app.services.subscription_service import (
    SubscriptionService,
)

router = APIRouter()


class CreateOrderRequest(BaseModel):
    planId: int


class CreateOrderResponse(BaseModel):
    orderNo: str
    planId: int
    planName: str
    amount: float
    payUrl: str
    status: str


@router.post(
    "/plans",
    response_model=SubscriptionPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_plan(
    plan: SubscriptionPlanCreate,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    service = SubscriptionService(db)
    return await service.create_plan(plan)


@router.get("/plans", response_model=list[SubscriptionPlanResponse])
async def list_plans(db: AsyncSession = Depends(get_db)):
    service = SubscriptionService(db)
    return await service.get_plans()


@router.post("/orders", response_model=CreateOrderResponse)
async def create_order(
    order_data: CreateOrderRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建支付订单，返回支付宝支付链接"""
    service = SubscriptionService(db)
    order = await service.create_order(
        user_id=current_user["user_id"],
        tenant_id=current_user["tenant_id"],
        plan_id=order_data.planId,
    )
    return order


@router.post("/subscribe", response_model=UserSubscriptionResponse)
async def subscribe(
    sub_data: SubscriptionCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SubscriptionService(db)
    return await service.subscribe_user(
        current_user["user_id"], current_user["tenant_id"], sub_data.plan_code
    )


@router.get("/my-subscription", response_model=UserSubscriptionResponse)
async def get_my_subscription(
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    service = SubscriptionService(db)
    sub = await service.get_user_subscription(current_user["user_id"])
    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription found")

    return sub


@router.post("/alipay-notify")
async def alipay_notify(request: Request, db: AsyncSession = Depends(get_db)):
    """支付宝异步回调通知"""
    form_data = await request.form()
    data = dict(form_data)

    service = SubscriptionService(db)
    success = await service.handle_alipay_notify(data)

    if success:
        return "success"
    else:
        return "fail"


@router.get("/alipay-return")
async def alipay_return(request: Request, db: AsyncSession = Depends(get_db)):
    """支付宝同步跳转回调 (浏览器)"""
    # 同步跳转我们只需解析参数并指引用户到成功页
    from fastapi.responses import RedirectResponse

    # 获取参数进行非严格验签（可选，一般跳转页只读参数）
    params = dict(request.query_params)
    out_trade_no = params.get("out_trade_no")

    # 重定向到前端成功页
    frontend_url = (
        os.getenv("FRONTEND_URL", "http://localhost:3000") + "/payment/success"
    )
    return RedirectResponse(url=f"{frontend_url}?orderNo={out_trade_no}")
