"""AI Strategy Service - 验证模型

验证相关的请求、响应和数据模型。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ValidationError(BaseModel):
    field: str = ""
    message: str = ""
    severity: str = "error"
    current_value: Any = None
    suggested_value: Any = None
    rule: str = ""


class ParameterValidationError(ValidationError):
    pass


class RangeRule(BaseModel):
    field: str
    min_value: float | None = None
    max_value: float | None = None
    rule: str = ""
    message: str = ""
    severity: str = "error"

    def validate(self, value: Any) -> bool:
        if value is None:
            return True
        try:
            val = float(value)
            if self.min_value is not None and val < self.min_value:
                return False
            if self.max_value is not None and val > self.max_value:
                return False
            return True
        except (TypeError, ValueError):
            return False


class CodeValidationRequest(BaseModel):
    code: str
    language: str = "python"


class CodeValidationResponse(BaseModel):
    is_valid: bool = True
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []
    quality_score: float = 0.0
    metrics: dict[str, Any] = {}
    validation_time: float = 0.0


class ParameterValidationRequest(BaseModel):
    parameters: dict[str, Any]
    include_suggestions: bool = True


class ParameterValidationResponse(BaseModel):
    is_valid: bool = True
    errors: list[ParameterValidationError] = []
    warnings: list[ParameterValidationError] = []
    suggestions: list[str] = []
    adjusted_parameters: dict[str, Any] = {}
    validation_time: float = 0.0


class BatchValidationRequest(BaseModel):
    items: list[dict[str, Any]]
    validation_type: str = "code"


class BatchValidationResponse(BaseModel):
    results: list[dict[str, Any]] = []
    total: int = 0
    passed: int = 0
    failed: int = 0
    validation_time: float = 0.0


class TemplateValidationRequest(BaseModel):
    template_id: str
    parameters: dict[str, Any] | None = None


class TemplateValidationResponse(BaseModel):
    is_valid: bool = True
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []
    template_id: str = ""
    validation_time: float = 0.0


CODE_QUALITY_METRICS: dict[str, Any] = {
    "cyclomatic_complexity": {"max": 10, "description": "圈复杂度"},
    "lines_of_code": {"max": 500, "description": "代码行数"},
    "comment_ratio": {"min": 0.1, "description": "注释比例"},
}

STRATEGY_PARAMETER_RULES: list[RangeRule] = [
    RangeRule(field="window", min_value=1, max_value=500, rule="1 <= window <= 500", message="窗口期应在 1~500 之间", severity="error"),
    RangeRule(field="threshold", min_value=0, max_value=1, rule="0 <= threshold <= 1", message="阈值应在 0~1 之间", severity="error"),
    RangeRule(field="top_k", min_value=1, max_value=500, rule="1 <= top_k <= 500", message="top_k 应在 1~500 之间", severity="error"),
]
