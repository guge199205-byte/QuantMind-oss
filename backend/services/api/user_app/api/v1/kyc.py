"""
KYC API Routes
实名认证API
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from backend.services.api.user_app.middleware.auth import get_current_user
from backend.services.api.user_app.services.kyc_service import KYCService
from backend.shared.database_manager_v2 import get_session

router = APIRouter(prefix="/kyc", tags=["实名认证"])


class KYCSubmitRequest(BaseModel):
    real_name: str = Field(..., min_length=2, max_length=50, description="真实姓名")
    id_number: str = Field(..., min_length=5, max_length=30, description="证件号码")
    document_type: str = Field("id_card", pattern="^(id_card|passport)$", description="证件类型")
    front_image_url: str | None = Field(None, description="证件正面URL")
    back_image_url: str | None = Field(None, description="证件背面URL")
    handheld_image_url: str | None = Field(None, description="手持证件URL")


class KYCResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    real_name: str
    id_number: str
    document_type: str
    rejection_reason: str | None
    submitted_at: str


@router.post("/submit", response_model=KYCResponse)
async def submit_kyc(
    request: KYCSubmitRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    提交实名认证信息
    """
    try:
        async with get_session(read_only=False) as session:
            kyc_service = KYCService(session)
            verification = await kyc_service.submit_verification(
                user_id=current_user["user_id"],
                tenant_id=current_user["tenant_id"],
                real_name=request.real_name,
                id_number=request.id_number,
                document_type=request.document_type,
                front_image_url=request.front_image_url,
                back_image_url=request.back_image_url,
                handheld_image_url=request.handheld_image_url,
            )
            return KYCResponse(
                id=verification.id,
                status=verification.status,
                real_name=verification.real_name,
                id_number=verification.id_number,  # Consider masking
                document_type=verification.document_type,
                rejection_reason=verification.rejection_reason,
                submitted_at=verification.submitted_at.isoformat(),
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/status", response_model=Optional[KYCResponse])
async def get_kyc_status(
    current_user: dict = Depends(get_current_user),
):
    """
    获取实名认证状态
    """
    async with get_session(read_only=True) as session:
        kyc_service = KYCService(session)
        verification = await kyc_service.get_verification(
            user_id=current_user["user_id"],
            tenant_id=current_user["tenant_id"],
        )
        if not verification:
            return None

        return KYCResponse(
            id=verification.id,
            status=verification.status,
            real_name=verification.real_name,
            id_number=verification.id_number,
            document_type=verification.document_type,
            rejection_reason=verification.rejection_reason,
            submitted_at=verification.submitted_at.isoformat(),
        )
