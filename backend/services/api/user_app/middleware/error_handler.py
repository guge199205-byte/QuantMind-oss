"""
Error Handler Middleware
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def add_error_handlers(app: FastAPI):
    """添加全局错误处理"""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """HTTP异常处理"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": exc.detail,
                "meta": {"path": str(request.url), "method": request.method},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """参数验证异常处理"""
        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "field": ".".join(str(x) for x in error["loc"]),
                    "message": error["msg"],
                }
            )

        return JSONResponse(
            status_code=422,
            content={
                "code": 422,
                "message": "参数验证失败",
                "errors": errors,
                "meta": {"path": str(request.url), "method": request.method},
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """通用异常处理"""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)

        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": "服务器内部错误",
                "meta": {"path": str(request.url), "method": request.method},
            },
        )
