"""
Authentication API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from backend.services.api.user_app.middleware.auth import get_current_user
from backend.services.api.user_app.schemas.user import (
    AdminLogin,
    CheckAvailabilityRequest,
    ForgotPasswordRequest,
    PasswordChangeRequest,
    PasswordResetRequest,
    PhoneLoginRequest,
    PhoneRegisterRequest,
    PhoneResetPasswordRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    VerificationRequest,
)
from backend.services.api.user_app.services import (
    AuthService,
    PasswordResetService,
    VerificationService,
)
from backend.services.api.user_app.services.user_service import UserService
from backend.shared.database_manager_v2 import get_session


from config.settings import settings

class RefreshTokenRequest(BaseModel):
    refresh_token: str


router = APIRouter(prefix="/auth")
is_oss = settings.edition == "oss"

def get_auth_service() -> AuthService:
    """获取认证服务"""
    return AuthService()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, auth_service: AuthService = Depends(get_auth_service)):
    """
    用户注册
    """
    try:
        return await auth_service.register(user_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    用户登录
    """
    try:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")
        return await auth_service.login(credentials, ip_address, user_agent)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: str | None = None,
    request: Request = None,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    用户登出
    """
    if not token and request:
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if token:
        await auth_service.logout(token)
    return None


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshTokenRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    令牌刷新
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    try:
        return await auth_service.refresh_tokens(payload.refresh_token, ip_address, user_agent)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

# 仅在非 OSS 模式下保留高级功能
if not is_oss:
    @router.post("/send-verification")
    async def send_verification(verification: VerificationRequest, request: Request):
        # ... (implementation kept for other editions)
        pass

    @router.post("/forgot-password")
    async def forgot_password(request_body: ForgotPasswordRequest):
        pass

    @router.post("/register/phone")
    async def register_by_phone(request: PhoneRegisterRequest):
        pass

    @router.post("/login/phone")
    async def login_by_phone(request: PhoneLoginRequest):
        pass

@router.post("/check-availability")
async def check_availability(
    request: CheckAvailabilityRequest,
    user_service: UserService = Depends(lambda: UserService()),
):
    """检查可用性"""
    exists = False
    if request.type == "username":
        user = await user_service.get_user_by_username(request.value, request.tenant_id)
        exists = user is not None
    elif request.type == "email":
        user = await user_service.get_user_by_email(request.value, request.tenant_id)
        exists = user is not None

    return {"code": 200, "message": "success", "data": {"available": not exists}}



@router.post("/change-password")
async def change_password(
    request_body: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    修改当前用户密码
    """
    try:
        await auth_service.change_password(
            user_id=current_user["user_id"],
            tenant_id=current_user["tenant_id"],
            old_password=request_body.old_password,
            new_password=request_body.new_password,
        )
        return {"code": 200, "message": "密码修改成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修改密码失败: {str(e)}")
