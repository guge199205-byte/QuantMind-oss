"""
Authentication API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from backend.services.api.user_app.middleware.auth import get_current_user
from backend.services.api.user_app.schemas.user import (
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
from backend.services.api.user_app.services.auth_service import AuthService
from backend.services.api.user_app.services.email_service import (
    PasswordResetService,
    VerificationService,
)
from backend.services.api.user_app.services.user_service import UserService
from backend.shared.database_manager_v2 import get_session


class RefreshTokenRequest(BaseModel):
    refresh_token: str


router = APIRouter(prefix="/auth")


def get_auth_service() -> AuthService:
    """获取认证服务"""
    return AuthService()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, auth_service: AuthService = Depends(get_auth_service)):
    """
    用户注册

    - **username**: 用户名 (3-128字符，只能包含字母和数字)
    - **email**: 邮箱地址
    - **password**: 密码 (至少8位)
    """
    try:
        return await auth_service.register(user_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试",
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    用户登录

    - **username**: 用户名或邮箱
    - **password**: 密码
    """
    try:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")
        return await auth_service.login(credentials, ip_address, user_agent)
    except ValueError as e:
        error_msg = str(e)
        if error_msg.startswith("MFA_REQUIRED:"):
            mfa_token = error_msg.split(":")[1]
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "code": 403,
                    "message": "mfa_required",
                    "data": {"mfa_token": mfa_token},
                },
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error_msg)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Login failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试",
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: str | None = None,
    request: Request = None,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    用户登出

    - **token**: 访问Token
    """
    if not token and request:
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少访问Token")

    await auth_service.logout(token)
    return None


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshTokenRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    使用刷新令牌获取新的访问令牌（自动轮换刷新令牌）
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    try:
        return await auth_service.refresh_tokens(payload.refresh_token, ip_address, user_agent)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post("/send-verification")
async def send_verification(verification: VerificationRequest, request: Request):
    """
    发送验证码（当前仅支持邮箱）
    """
    from backend.services.api.user_app.models.user import User

    if verification.type != "email":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="当前仅支持邮箱验证码",
        )

    async with get_session(read_only=False) as session:
        verification_service = VerificationService(session)
        target_user_id = verification.user_id

        if not target_user_id:
            if verification.purpose == "register":
                target_user_id = f"register:{verification.tenant_id}:{verification.identifier.lower()}"
            else:
                result = await session.execute(
                    select(User).where(
                        User.email == verification.identifier,
                        User.tenant_id == verification.tenant_id,
                    )
                )
                user = result.scalar_one_or_none()
                if not user:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
                target_user_id = user.user_id

        ip_address = request.client.host if request.client else None
        await verification_service.create_verification_code(
            target_user_id,
            verification.tenant_id,
            verification.identifier,
            verification.purpose,
            ip_address=ip_address,
        )

    return {"code": 200, "message": "验证码已发送"}


@router.post("/forgot-password")
async def forgot_password(request_body: ForgotPasswordRequest):
    """
    请求密码重置链接
    """
    async with get_session(read_only=False) as session:
        reset_service = PasswordResetService(session)
        await reset_service.request_password_reset(request_body.email, request_body.tenant_id)

    return {"code": 200, "message": "如果邮箱存在，已发送重置邮件"}


@router.post("/reset-password")
async def reset_password(
    request_body: PasswordResetRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    重置密码
    """
    auth_service._validate_password(request_body.new_password)

    async with get_session(read_only=False) as session:
        reset_service = PasswordResetService(session)
        success, detail = await reset_service.reset_password(
            request_body.token, request_body.tenant_id, request_body.new_password
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail or "重置失败",
            )

    return {"code": 200, "message": "密码已重置"}


@router.post("/register/phone", response_model=TokenResponse)
async def register_by_phone(
    request: PhoneRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """手机号注册"""
    try:
        return await auth_service.register_by_phone(
            request.phone, request.code, request.password, request.tenant_id, request.username
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login/phone", response_model=TokenResponse)
async def login_by_phone(
    request: PhoneLoginRequest,
    req: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    """手机验证码登录"""
    ip = req.client.host if req.client else None
    ua = req.headers.get("user-agent")
    try:
        return await auth_service.login_by_phone(request.phone, request.code, request.tenant_id, ip, ua)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/password/reset/phone")
async def reset_password_by_phone(
    request: PhoneResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """手机号重置密码"""
    try:
        await auth_service.reset_password_by_phone(request.phone, request.code, request.new_password, request.tenant_id)
        return {"code": 200, "message": "密码已重置"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/check-availability")
async def check_availability(
    request: CheckAvailabilityRequest,
    user_service: UserService = Depends(lambda: UserService()),
):
    """检查用户名、手机号或邮箱是否已存在"""
    exists = False
    if request.type == "username":
        user = await user_service.get_user_by_username(request.value, request.tenant_id)
        exists = user is not None
    elif request.type == "phone":
        user = await user_service.get_user_by_phone(request.value, request.tenant_id)
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
