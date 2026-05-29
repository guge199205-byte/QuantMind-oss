"""
KYC Service
实名认证服务
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select

from backend.services.api.user_app.models.kyc import IdentityVerification

logger = logging.getLogger(__name__)


class KYCService:
    def __init__(self, session):
        self.session = session

    async def get_verification(self, user_id: str, tenant_id: str) -> IdentityVerification | None:
        """获取用户的实名认证记录"""
        result = await self.session.execute(
            select(IdentityVerification).where(
                IdentityVerification.user_id == user_id,
                IdentityVerification.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def submit_verification(
        self,
        user_id: str,
        tenant_id: str,
        real_name: str,
        id_number: str,
        document_type: str = "id_card",
        front_image_url: str | None = None,
        back_image_url: str | None = None,
        handheld_image_url: str | None = None,
    ) -> IdentityVerification:
        """提交实名认证"""
        # Check if already submitted
        existing = await self.get_verification(user_id, tenant_id)
        if existing:
            if existing.status == "verified":
                raise ValueError("用户已通过实名认证")
            if existing.status == "pending":
                raise ValueError("认证审核中，请勿重复提交")

            # If rejected, update existing
            existing.real_name = real_name
            existing.id_number = id_number
            existing.document_type = document_type
            existing.front_image_url = front_image_url
            existing.back_image_url = back_image_url
            existing.handheld_image_url = handheld_image_url
            existing.status = "pending"
            existing.submitted_at = datetime.now()
            existing.rejection_reason = None
            await self.session.commit()
            return existing

        # Create new
        verification = IdentityVerification(
            user_id=user_id,
            tenant_id=tenant_id,
            real_name=real_name,
            id_number=id_number,
            document_type=document_type,
            front_image_url=front_image_url,
            back_image_url=back_image_url,
            handheld_image_url=handheld_image_url,
            status="pending",
        )
        self.session.add(verification)
        await self.session.commit()
        return verification

    async def review_verification(
        self,
        user_id: str,
        tenant_id: str,
        verified: bool,
        reason: str | None = None,
        reviewer_id: str | None = None,
    ) -> IdentityVerification:
        """审核实名认证 (Admin)"""
        verification = await self.get_verification(user_id, tenant_id)
        if not verification:
            raise ValueError("认证记录不存在")

        if verification.status != "pending":
            raise ValueError(f"当前状态不可审核: {verification.status}")

        if verified:
            verification.status = "verified"
            verification.verified_at = datetime.now()
            verification.verified_by = reviewer_id
        else:
            verification.status = "rejected"
            verification.rejection_reason = reason
            verification.verified_at = datetime.now()
            verification.verified_by = reviewer_id

        await self.session.commit()
        return verification
