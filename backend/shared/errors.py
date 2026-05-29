from __future__ import annotations

from enum import IntEnum


class ErrorCode(IntEnum):
    # 通用
    PARAM_REQUIRED = 1000
    PARAM_INVALID = 1001
    UNAUTHORIZED = 2000
    FORBIDDEN = 2001
    NOT_FOUND = 3000
    STATE_INVALID = 3001
    STRATEGY_GEN_FAILED = 4000
    DSL_VALIDATE_FAILED = 4001
    STRATEGY_SECURITY_VIOLATION = 4002
    BACKTEST_JOB_NOT_FOUND = 4100
    BACKTEST_JOB_RUNNING = 4101
    BACKTEST_RESOURCE_LIMIT = 4102
    UPLOAD_FAILED = 4200
    FILE_NOT_FOUND = 4201
    DELETE_FAILED = 4202
    LIST_FAILED = 4203
    FILE_TYPE_NOT_SUPPORTED = 4204
    FILE_SIZE_EXCEEDED = 4205
    EXTERNAL_UPSTREAM_ERROR = 5000
    LLM_TIMEOUT = 5001
    INTERNAL_ERROR = 9000


ERROR_MESSAGES = {
    ErrorCode.PARAM_REQUIRED: "parameter required",
    ErrorCode.PARAM_INVALID: "parameter invalid",
    ErrorCode.UNAUTHORIZED: "unauthorized",
    ErrorCode.FORBIDDEN: "forbidden",
    ErrorCode.NOT_FOUND: "resource not found",
    ErrorCode.STATE_INVALID: "state not allowed",
    ErrorCode.STRATEGY_GEN_FAILED: "strategy generation failed",
    ErrorCode.DSL_VALIDATE_FAILED: "strategy DSL validation failed",
    ErrorCode.STRATEGY_SECURITY_VIOLATION: "strategy security violation",
    ErrorCode.BACKTEST_JOB_NOT_FOUND: "backtest job not found",
    ErrorCode.BACKTEST_JOB_RUNNING: "backtest job running",
    ErrorCode.BACKTEST_RESOURCE_LIMIT: "backtest resource limit",
    ErrorCode.UPLOAD_FAILED: "file upload failed",
    ErrorCode.FILE_NOT_FOUND: "file not found",
    ErrorCode.DELETE_FAILED: "file delete failed",
    ErrorCode.LIST_FAILED: "file list failed",
    ErrorCode.FILE_TYPE_NOT_SUPPORTED: "file type not supported",
    ErrorCode.FILE_SIZE_EXCEEDED: "file size exceeded",
    ErrorCode.EXTERNAL_UPSTREAM_ERROR: "external upstream error",
    ErrorCode.LLM_TIMEOUT: "llm provider timeout",
    ErrorCode.INTERNAL_ERROR: "internal server error",
}


def get_error_message(code: ErrorCode) -> str:
    return ERROR_MESSAGES.get(code, "unknown error")
