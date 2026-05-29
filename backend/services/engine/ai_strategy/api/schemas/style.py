"""AI 策略向导 - 风格配置相关 Schema 定义"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


class ApplyStyleRequest(BaseModel):
    style: Literal["conservative", "aggressive", "dynamic"]
    custom_overrides: dict[str, Any] | None = None


class ApplyStyleResponse(BaseModel):
    applied_risk_config: dict[str, Any]
    style_description: str
    warnings: list[str] = []
