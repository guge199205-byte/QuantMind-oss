"""AI 策略向导 - 股票池相关 Schema 定义"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class NumericCondition(BaseModel):
    type: Literal["numeric"] = "numeric"
    factor: str
    operator: str
    threshold: float


class TrendCondition(BaseModel):
    type: Literal["trend"] = "trend"
    factor: str
    window: int
    direction: str


class CompositeCondition(BaseModel):
    type: Literal["composite"] = "composite"
    op: str
    children: list[dict[str, Any]]


Condition = dict[str, Any]


class ParseRequest(BaseModel):
    conditions: Condition


class ParseResponse(BaseModel):
    dsl: str
    mapping: dict[str, Any] = {}
    warnings: list[str] = []
    confidence: float = 0.92
    suggestions: list[str] = []
    version: str = "1.0.0"


class QueryPoolRequest(BaseModel):
    dsl: str


class PoolItem(BaseModel):
    symbol: str
    name: str | None = None
    metrics: dict[str, float] = {}


class QueryPoolResponse(BaseModel):
    items: list[PoolItem]
    summary: dict[str, Any] = {}
    charts: dict[str, Any] = {}


class SavePoolFileRequest(BaseModel):
    tenant_id: str | None = None
    user_id: str
    pool_name: str
    format: Literal["json", "txt", "csv"] = "txt"
    pool: list[dict[str, Any]]


class SavePoolFileResponse(BaseModel):
    success: bool
    pool_name: str | None = None
    file_url: str | None = None
    file_key: str | None = None
    relative_path: str | None = None
    file_size: int | None = None
    code_hash: str | None = None
    error: str | None = None


class DeletePoolFileRequest(BaseModel):
    user_id: str | None = None
    file_url: str | None = None
    file_key: str | None = None


class DeletePoolFileResponse(BaseModel):
    success: bool
    error: str | None = None


class ListPoolFilesRequest(BaseModel):
    tenant_id: str | None = None
    user_id: str
    limit: int = Field(default=100, ge=1, le=200)


class PoolFileSummary(BaseModel):
    id: int
    tenant_id: str | None = None
    user_id: str
    pool_name: str | None = None
    file_key: str
    file_url: str | None = None
    relative_path: str | None = None
    format: str | None = None
    file_size: int | None = None
    code_hash: str | None = None
    stock_count: int | None = None
    created_at: str | None = None
    is_active: bool | None = None


class ListPoolFilesResponse(BaseModel):
    success: bool
    pools: list[PoolFileSummary] = []
    error: str | None = None


class PreviewPoolFileRequest(BaseModel):
    tenant_id: str | None = None
    user_id: str
    file_key: str


class PreviewPoolFileResponse(BaseModel):
    success: bool
    items: list[PoolItem] = []
    summary: dict[str, Any] = {}
    charts: dict[str, Any] = {}
    pool_file: dict[str, Any] | None = None
    error: str | None = None


class GetActivePoolFileRequest(BaseModel):
    tenant_id: str | None = None
    user_id: str


class GetActivePoolFileResponse(BaseModel):
    success: bool
    pool_file: dict[str, Any] | None = None
    error: str | None = None


# --- Phase A: New Pool Refactoring Schemas ---

class WorkingPool(BaseModel):
    user_id: str
    items: list[PoolItem]
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class SaveWorkingPoolRequest(BaseModel):
    items: list[PoolItem]


class ActivatePoolVersionRequest(BaseModel):
    version_id: int
