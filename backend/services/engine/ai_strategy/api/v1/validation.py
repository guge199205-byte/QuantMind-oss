"""AI Strategy V1 Qlib 验证与修复路由"""

import asyncio
import logging
import os
import re
from typing import List

from fastapi import APIRouter

from ...services.llm_resilience import get_resilient_llm_router
from ...services.qlib_validator import get_qlib_validator
from ..schemas import (
    RepairQlibRequest,
    RepairQlibResponse,
    ValidateQlibRequest,
    ValidateQlibResponse,
    ValidationCheckResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _strip_markdown_fences(code: str) -> str:
    """将 LLM 返回的 markdown 代码围栏剥离为纯 Python。"""
    if not code:
        return code
    s = code.strip()
    if "```" not in s:
        return s + "\n"
    try:
        m = re.search(r"```(?:python)?\s*(.*?)\s*```", s, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return (m.group(1) or "").strip() + "\n"
    except Exception:
        pass
    lines = [ln for ln in s.splitlines() if not ln.strip().startswith("```")]
    return "\n".join(lines).strip() + "\n"


def _repair_prompt(code: str, err: str) -> str:
    return (
        "下面是一段 Python 代码，存在语法错误："
        f"{err}\n\n"
        "请你修复它，要求：\n"
        "1. 输出必须是完整的 Python 代码文件\n"
        "2. 保持原有功能和结构，尽量少改动\n"
        "3. 不要输出 markdown 代码块，不要解释，只输出代码\n\n"
        "待修复代码：\n"
        f"{code}"
    ).strip()


@router.post("/validate-qlib", response_model=ValidateQlibResponse)
async def validate_qlib_code(body: ValidateQlibRequest):
    """验证 Qlib 策略代码"""
    try:
        validator = get_qlib_validator()
        normalized_code = _strip_markdown_fences(body.code)
        result = await validator.validate_code(normalized_code, body.context, mode=body.mode)

        checks = [ValidationCheckResponse(**check.to_dict()) for check in result.checks]

        logger.info(
            "Qlib validation completed: valid=%s, checks=%s, warnings=%s",
            result.valid,
            len(result.checks),
            len(result.warnings),
        )

        return ValidateQlibResponse(
            success=True,
            valid=result.valid,
            checks=checks,
            warnings=result.warnings,
            execution_preview=result.execution_preview,
        )
    except Exception as e:
        logger.error("Qlib validation failed: %s", e, exc_info=True)
        return ValidateQlibResponse(success=False, valid=False, checks=[], error=f"验证失败: {str(e)}")


@router.post("/repair-qlib", response_model=RepairQlibResponse)
async def repair_qlib_code(body: RepairQlibRequest):
    """使用大模型尝试修复 Qlib 策略代码的语法/结构问题"""
    try:
        validator = get_qlib_validator()
        provider_name = (os.getenv("LLM_PROVIDER_FORCE") or os.getenv("LLM_PROVIDER") or "qwen").strip().lower()
        llm_router = get_resilient_llm_router()

        code = _strip_markdown_fences(body.code)
        attempts = 0
        last_checks: list[ValidationCheckResponse] = []
        last_warnings: list[str] = []

        for i in range(int(body.max_rounds)):
            attempts = i + 1
            result = await validator.validate_code(code, context=None, mode="syntax_only")
            last_checks = [ValidationCheckResponse(**c.to_dict()) for c in result.checks]
            last_warnings = list(result.warnings or [])
            if result.valid:
                return RepairQlibResponse(
                    success=True,
                    valid=True,
                    code=code,
                    attempts=attempts,
                    checks=last_checks,
                    warnings=last_warnings,
                )

            err_parts: list[str] = []
            for c in result.checks:
                if not c.passed:
                    err_parts.append(f"{c.message} | {c.details}" if c.details else c.message)
            err_msg = body.error or "; ".join([p for p in err_parts if p]) or "语法错误"

            fixed, _meta = await asyncio.to_thread(
                llm_router.generate_code,
                _repair_prompt(code, err_msg),
                provider_name,
                "simple",
            )
            code = _strip_markdown_fences(fixed)

        final_result = await validator.validate_code(code, context=None, mode="syntax_only")
        last_checks = [ValidationCheckResponse(**c.to_dict()) for c in final_result.checks]
        last_warnings = list(final_result.warnings or [])
        if final_result.valid:
            return RepairQlibResponse(
                success=True,
                valid=True,
                code=code,
                attempts=attempts,
                checks=last_checks,
                warnings=last_warnings,
            )

        return RepairQlibResponse(
            success=True,
            valid=False,
            code=code,
            attempts=attempts,
            checks=last_checks,
            warnings=last_warnings,
            error=f"AI 修复已尝试 {attempts} 轮（provider={provider_name}），但仍未通过语法检查",
        )
    except Exception as e:
        logger.error("Qlib repair failed: %s", e, exc_info=True)
        return RepairQlibResponse(
            success=False,
            valid=False,
            code=_strip_markdown_fences(body.code),
            attempts=0,
            checks=[],
            warnings=[],
            error=f"修复失败: {str(e)}",
        )
