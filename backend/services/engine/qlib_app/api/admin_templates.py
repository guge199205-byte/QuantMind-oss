"""
管理员策略模板 CRUD API
提供对 strategy_templates/ 目录的增删改查操作。
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, field_validator

from backend.services.engine.qlib_app.services.strategy_templates import (
    StrategyTemplate,
    _resolve_templates_dir,
    get_all_templates,
    invalidate_templates_cache,
)
from backend.shared.auth import get_internal_call_secret
from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

logger = logging.getLogger(__name__)
task_logger = StructuredTaskLogger(logger, "AdminTemplatesAPI")

router = APIRouter()

_INTERNAL_SECRET = get_internal_call_secret()
_MAX_CODE_BYTES = 200 * 1024  # 200 KB
_ID_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")


# ---------------------------------------------------------------------------
# 鉴权依赖
# ---------------------------------------------------------------------------


def _verify_internal(x_internal_call: str | None = Header(None)) -> None:
    """校验内部调用 Secret，防止外部直接访问。"""
    if not _INTERNAL_SECRET or x_internal_call != _INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="内部调用凭证无效")


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class TemplateParam(BaseModel):
    name: str
    description: str
    default: Any
    min: float | None = None
    max: float | None = None


class TemplateCreateRequest(BaseModel):
    id: str | None = None  # POST 可选，PUT 路径中提供
    name: str
    description: str
    category: str  # basic | advanced | risk_control
    difficulty: str  # beginner | intermediate | advanced
    code: str
    params: list[TemplateParam] = []
    execution_defaults: dict[str, Any] = {}
    live_defaults: dict[str, Any] = {}
    live_config_tips: list[str] = []

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"basic", "advanced", "risk_control"}
        if v not in allowed:
            raise ValueError(f"category 必须是 {allowed} 之一")
        return v

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        allowed = {"beginner", "intermediate", "advanced"}
        if v not in allowed:
            raise ValueError(f"difficulty 必须是 {allowed} 之一")
        return v


def _slug(name: str) -> str:
    """将中英文名称转为合法 id（snake_case）。"""
    slug = re.sub(r"[^a-z0-9]", "_", name.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:64] or "template"


def _validate_id(template_id: str) -> None:
    if not _ID_PATTERN.match(template_id):
        raise HTTPException(
            status_code=422,
            detail=f"模板 ID 只允许小写字母、数字和下划线，长度 1-64，收到: {template_id!r}",
        )


def _get_file_pair(template_id: str) -> tuple[Path, Path]:
    templates_dir = _resolve_templates_dir()
    return (
        templates_dir / f"{template_id}.json",
        templates_dir / f"{template_id}.py",
    )


def _write_template(template_id: str, data: TemplateCreateRequest) -> None:
    """将模板写入 .json + .py 文件对。"""
    json_path, py_path = _get_file_pair(template_id)

    # 代码大小检查
    code_bytes = data.code.encode("utf-8")
    if len(code_bytes) > _MAX_CODE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"策略代码超过 200KB 限制（实际 {len(code_bytes)} bytes）",
        )

    metadata = {
        "id": template_id,
        "name": data.name,
        "description": data.description,
        "category": data.category,
        "difficulty": data.difficulty,
        "params": [p.model_dump() for p in data.params],
        "execution_defaults": data.execution_defaults,
        "live_defaults": data.live_defaults,
        "live_config_tips": data.live_config_tips,
    }

    templates_dir = _resolve_templates_dir()
    templates_dir.mkdir(parents=True, exist_ok=True)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    with open(py_path, "w", encoding="utf-8") as f:
        f.write(data.code)

    invalidate_templates_cache()
    task_logger.info("template_written", "策略模板写入完成", template_id=template_id)


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------


@router.get("")
async def list_admin_templates(
    x_internal_call: str | None = Header(None),
):
    """列出所有策略模板（含完整代码，供管理员使用）。"""
    _verify_internal(x_internal_call)
    invalidate_templates_cache()  # 管理员查看时始终拿最新数据
    templates = get_all_templates()
    return {
        "total": len(templates),
        "templates": [t.model_dump() for t in templates],
    }


@router.post("", status_code=201)
async def create_template(
    data: TemplateCreateRequest,
    x_internal_call: str | None = Header(None),
):
    """新建策略模板（写 .json + .py 文件）。"""
    _verify_internal(x_internal_call)

    # 生成或校验 ID
    template_id = (data.id or _slug(data.name)).lower()
    _validate_id(template_id)

    json_path, _ = _get_file_pair(template_id)
    if json_path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"模板 ID '{template_id}' 已存在，请使用不同的 ID 或通过 PUT 更新",
        )

    _write_template(template_id, data)
    return {"success": True, "id": template_id, "message": f"模板 '{data.name}' 创建成功"}


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    data: TemplateCreateRequest,
    x_internal_call: str | None = Header(None),
):
    """更新策略模板（覆盖 .json + .py 文件）。"""
    _verify_internal(x_internal_call)
    _validate_id(template_id)

    json_path, _ = _get_file_pair(template_id)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"模板 '{template_id}' 不存在")

    _write_template(template_id, data)
    return {"success": True, "id": template_id, "message": f"模板 '{data.name}' 更新成功"}


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    x_internal_call: str | None = Header(None),
):
    """删除策略模板（删除 .json + .py 文件）。"""
    _verify_internal(x_internal_call)
    _validate_id(template_id)

    json_path, py_path = _get_file_pair(template_id)
    if not json_path.exists() and not py_path.exists():
        raise HTTPException(status_code=404, detail=f"模板 '{template_id}' 不存在")

    errors = []
    for path in (json_path, py_path):
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            errors.append(str(e))

    invalidate_templates_cache()

    if errors:
        task_logger.warning("template_delete_partial_error", "删除模板时出现部分错误", template_id=template_id, errors=errors)

    task_logger.info("template_deleted", "策略模板已删除", template_id=template_id)
    return {"success": True, "id": template_id, "message": f"模板 '{template_id}' 已删除"}
