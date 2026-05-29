from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ============ Request Models ============


class ApiKeyCreate(BaseModel):
    """Create API Key Request"""

    name: str = Field(..., min_length=1, max_length=100, description="Key Name/Label")
    permissions: list[str] = Field(default=[], description="List of permissions (scopes)")
    expires_at: datetime | None = Field(None, description="Expiration time")


class ApiKeyUpdate(BaseModel):
    """Update API Key Request"""

    name: str | None = Field(None, min_length=1, max_length=100)
    permissions: list[str] | None = Field(None)
    is_active: bool | None = Field(None)


# ============ Response Models ============


class ApiKeyResponse(BaseModel):
    """API Key Response (showing secret only once)"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    access_key: str
    secret_key: str = Field(..., description="Secret Key (only returned on creation)")
    name: str
    permissions: list[str]
    is_active: bool
    created_at: datetime
    expires_at: datetime | None


class ApiKeyInfo(BaseModel):
    """API Key Info (no secret)"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    access_key: str
    name: str
    permissions: list[str]
    is_active: bool
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None


class ApiKeyListResponse(BaseModel):
    """List of API Keys"""

    items: list[ApiKeyInfo]
    count: int


class ApiKeyBootstrapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    access_key: str
    name: str
    permissions: list[str]
    is_active: bool
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    secret_key: str | None = None
    just_created: bool = False


class ApiKeyRotateSecretResponse(BaseModel):
    access_key: str
    secret_key: str
