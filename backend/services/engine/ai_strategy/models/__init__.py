"""AI Strategy Service - 共享请求/响应模型

所有路由共用的 Pydantic 模型定义。
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# LLM Provider 请求/响应
# =============================================================================


class StrategyGenReq(BaseModel):
    description: str
    user_id: str = "desktop-user"
    provider: str | None = None
    examples: list[str] | None = None


class StrategyGenRes(BaseModel):
    strategy_name: str = ""
    rationale: str = ""
    code: str = ""
    provider: str = ""


class StrategyConversionRequest(BaseModel):
    code: str
    target_platform: str = "qlib"
    user_id: str = "desktop-user"


class StrategyConversionResponse(BaseModel):
    success: bool = True
    converted_code: str = ""
    conversion_notes: list[str] = []
    warnings: list[str] = []
    suggestions: list[str] = []
    platform_differences: list[str] = []
    estimated_compatibility: float = 1.0


class StrategyGenerationRequest(BaseModel):
    description: str
    user_id: str = "desktop-user"
    provider: str | None = None
    examples: list[str] | None = None


class StrategyCodeArtifact(BaseModel):
    filename: str
    language: str
    code: str


class StrategyMetadata(BaseModel):
    factors: list[str] = []
    risk_controls: list[str] = []
    assumptions: list[str] = []
    notes: str = ""


class StrategyGenerationResult(BaseModel):
    strategy_name: str
    rationale: str
    artifacts: list[StrategyCodeArtifact] = []
    metadata: StrategyMetadata | None = None
    provider: str = ""


# =============================================================================
# 策略操作
# =============================================================================


class StrategyRefineRequest(BaseModel):
    feedback: str
    current_code: str
    user_id: str = "desktop-user"
    provider: str | None = None


class StrategyAnalysisRequest(BaseModel):
    analysis_type: str = "performance"
    user_id: str = "desktop-user"


class StrategyExecutionRequest(BaseModel):
    execution_config: dict[str, Any] | None = None
    user_id: str = "desktop-user"


# =============================================================================
# 聊天
# =============================================================================


class ChatRequest(BaseModel):
    message: str
    user_id: str = "desktop-user"
    provider: str | None = None


# =============================================================================
# 验证相关
# =============================================================================


class CodeValidationRequest(BaseModel):
    code: str
    language: str = "python"


class ParameterValidationRequest(BaseModel):
    parameters: dict[str, Any]
    include_suggestions: bool = True


class BatchValidationRequest(BaseModel):
    items: list[dict[str, Any]]
    validation_type: str = "code"


class TemplateValidationRequest(BaseModel):
    template_id: str
    parameters: dict[str, Any] | None = None


# =============================================================================
# 模板相关
# =============================================================================


class TemplateMatchRequest(BaseModel):
    description: str
    user_id: str = "desktop-user"
    top_k: int = 5


class TemplateMatchResponse(BaseModel):
    templates: list[dict[str, Any]] = []
    matched: bool = False


class TemplateSearchFilter(BaseModel):
    keyword: str | None = None
    category: str | None = None
    risk_level: str | None = None
    market: str | None = None
    complexity: str | None = None
    tags: list[str] | None = None


class StrategyTemplate(BaseModel):
    id: str
    name: str
    description: str
    category: str = "generic"
    risk_level: str = "medium"
    market: str = "CN"
    timeframe: str = "1d"
    parameters: dict[str, Any] = {}
    code: str = ""
    tags: list[str] = []


class TemplateMatch(BaseModel):
    template: StrategyTemplate
    score: float = 0.0
    matched_fields: list[str] = []
    explanation: str = ""


BUILTIN_TEMPLATES: list[StrategyTemplate] = []


def get_template_by_id(template_id: str) -> StrategyTemplate | None:
    """根据 ID 获取模板"""
    for t in BUILTIN_TEMPLATES:
        if t.id == template_id:
            return t
    return None


def search_templates(
    query: str | None = None,
    keyword: str | None = None,
    category: str | None = None,
    risk_level: str | None = None,
    market: str | None = None,
    complexity: str | None = None,
    tags: list[str] | None = None,
    limit: int = 20,
    page: int = 1,
    page_size: int = 20,
) -> Any:
    """模板搜索 stub"""
    from types import SimpleNamespace

    return SimpleNamespace(
        templates=[],
        total=0,
        page=page,
        page_size=page_size,
        total_pages=0,
        search_time=0.0,
    )


# =============================================================================
# Validation submodule classes (models.validation)
# =============================================================================


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


class CodeValidationResponse(BaseModel):
    is_valid: bool = True
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []
    quality_score: float = 0.0
    metrics: dict[str, Any] = {}
    validation_time: float = 0.0


class ParameterValidationResponse(BaseModel):
    is_valid: bool = True
    errors: list[ParameterValidationError] = []
    warnings: list[ParameterValidationError] = []
    suggestions: list[str] = []
    adjusted_parameters: dict[str, Any] = {}
    validation_time: float = 0.0


class BatchValidationResponse(BaseModel):
    results: list[dict[str, Any]] = []
    total: int = 0
    passed: int = 0
    failed: int = 0
    validation_time: float = 0.0


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
