"""
Password Reset API Routes
密码重置API路由
"""

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from backend.services.api.user_app.database import get_db
from backend.services.api.user_app.services.email_service import PasswordResetService

router = APIRouter(prefix="/auth/password")


class PasswordResetRequest(BaseModel):
    """密码重置请求"""

    tenant_id: str = Field(..., min_length=1, max_length=64, description="租户ID")
    email: EmailStr = Field(..., description="注册邮箱")


class PasswordResetConfirm(BaseModel):
    """密码重置确认"""

    token: str = Field(..., description="重置令牌")
    tenant_id: str = Field(..., min_length=1, max_length=64, description="租户ID")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")


class ResponseModel(BaseModel):
    """统一响应模型"""

    code: int = 200
    message: str = "success"
    data: dict = {}


@router.post("/reset-request", response_model=ResponseModel)
async def request_password_reset(request_data: PasswordResetRequest, db=Depends(get_db)):
    """
    请求密码重置

    - 发送密码重置邮件
    - 即使邮箱不存在也返回成功（防止用户枚举）
    """
    reset_service = PasswordResetService(db)

    await reset_service.request_password_reset(request_data.email, request_data.tenant_id)

    return {
        "code": 200,
        "message": "如果该邮箱已注册，您将收到密码重置邮件",
        "data": {},
    }


@router.post("/reset-confirm", response_model=ResponseModel)
async def confirm_password_reset(confirm_data: PasswordResetConfirm, db=Depends(get_db)):
    """
    确认密码重置

    - 使用令牌重置密码
    """
    reset_service = PasswordResetService(db)

    success, error = await reset_service.reset_password(
        confirm_data.token, confirm_data.tenant_id, confirm_data.new_password
    )

    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    return {"code": 200, "message": "密码重置成功", "data": {}}


@router.post("/verify-token", response_model=ResponseModel)
async def verify_reset_token(
    token: str = Body(..., embed=True),
    tenant_id: str = Body(..., embed=True),
    db=Depends(get_db),
):
    """
    验证重置令牌

    - 检查令牌是否有效
    - 用于前端验证
    """
    reset_service = PasswordResetService(db)

    success, result = await reset_service.verify_reset_token(token, tenant_id)

    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

    return {"code": 200, "message": "令牌有效", "data": {"user_id": result}}
