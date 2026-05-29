from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from backend.services.api.models.base import Base


class ApiKey(Base):
    """API Key Model"""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")
    user_id = Column(String(64), nullable=False, index=True, comment="User ID")
    tenant_id = Column(String(64), nullable=False, index=True, comment="Tenant ID")

    # Key details
    access_key = Column(
        String(64), unique=True, nullable=False, index=True, comment="Access Key"
    )
    secret_hash = Column(String(255), nullable=False, comment="Secret Key Hash")
    name = Column(String(100), comment="Key Name/Label")
    permissions = Column(JSON, default=[], comment="Permissions/Scopes")

    # Status
    is_active = Column(Boolean, default=True, comment="Is Active")

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), comment="Created At"
    )
    expires_at = Column(DateTime(timezone=True), nullable=True, comment="Expires At")
    last_used_at = Column(
        DateTime(timezone=True), nullable=True, comment="Last Used At"
    )

    __table_args__ = (UniqueConstraint("access_key", name="uq_api_keys_access_key"),)

    def __repr__(self):
        return f"<ApiKey(access_key={self.access_key}, name={self.name})>"
