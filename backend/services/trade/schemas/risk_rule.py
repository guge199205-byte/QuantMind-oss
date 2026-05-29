"""
Risk Rule Schemas
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RiskRuleBase(BaseModel):
    """Base risk rule schema"""

    rule_name: str = Field(..., min_length=1, max_length=100)
    rule_type: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(None, max_length=500)
    parameters: dict[str, Any] = Field(default_factory=dict)
    applies_to_all: bool = True
    user_ids: list[int] | None = None
    priority: int = Field(0, ge=0, le=100)


class RiskRuleCreate(RiskRuleBase):
    """Create risk rule schema"""

    is_active: bool = True


class RiskRuleUpdate(BaseModel):
    """Update risk rule schema"""

    rule_name: str | None = Field(None, min_length=1, max_length=100)
    rule_type: str | None = Field(None, min_length=1, max_length=50)
    description: str | None = Field(None, max_length=500)
    is_active: bool | None = None
    parameters: dict[str, Any] | None = None
    applies_to_all: bool | None = None
    user_ids: list[int] | None = None
    priority: int | None = Field(None, ge=0, le=100)


class RiskRuleResponse(RiskRuleBase):
    """Risk rule response schema"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
