"""
KYC / Identity Verification Models
实名认证模型
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from backend.services.api.user_app.models.user import Base


class IdentityVerification(Base):
    """实名认证表"""

    __tablename__ = "identity_verifications"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")
    user_id = Column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
        comment="用户ID",
    )
    tenant_id = Column(String(64), nullable=False, index=True, comment="租户ID")

    # 身份信息
    real_name = Column(String(128), nullable=False, comment="真实姓名")
    id_number = Column(String(128), nullable=False, index=True, comment="证件号码")
    document_type = Column(
        String(32), default="id_card", comment="证件类型: id_card/passport"
    )

    # 文件存储 (URL)
    front_image_url = Column(String(512), comment="证件正面URL")
    back_image_url = Column(String(512), comment="证件背面URL")
    handheld_image_url = Column(String(512), comment="手持证件URL")

    # 状态
    status = Column(
        String(32),
        default="pending",
        index=True,
        comment="状态: pending/verified/rejected",
    )
    rejection_reason = Column(Text, comment="拒绝原因")

    # 审计
    submitted_at = Column(
        DateTime(timezone=True), server_default=func.now(), comment="提交时间"
    )
    verified_at = Column(DateTime(timezone=True), comment="审核时间")
    verified_by = Column(String(64), comment="审核人ID")

    def __repr__(self):
        return f"<IdentityVerification(user_id={self.user_id}, status={self.status})>"
