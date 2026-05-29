"""
API规范和模型定义.
定义API接口规范和数据模型.
"""

import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    """服务状态."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheckResponse(BaseModel):
    """健康检查响应."""

    status: ServiceStatus
    service: str
    version: str | None = None
    details: dict[str, Any] | None = None


class ErrorCode(Enum):
    """错误码枚举"""

    # 通用错误 (1000-1999)
    SUCCESS = 1000  # 操作成功
    UNKNOWN_ERROR = 1001  # 未知错误
    VALIDATION_ERROR = 1002  # 验证错误
    AUTHENTICATION_ERROR = 1003  # 认证错误
    AUTHORIZATION_ERROR = 1004  # 授权错误
    RATE_LIMIT_EXCEEDED = 1005  # 速率限制
    RESOURCE_NOT_FOUND = 1006  # 资源不存在
    CONFLICT_ERROR = 1007  # 冲突错误
    INTERNAL_ERROR = 1008  # 内部错误

    # 服务错误 (2000-2999)
    SERVICE_UNAVAILABLE = 2001  # 服务不可用
    SERVICE_TIMEOUT = 2002  # 服务超时
    SERVICE_ERROR = 2003  # 服务错误

    # 业务错误 (3000-3999)
    BUSINESS_RULE_VIOLATION = 3001  # 业务规则违反
    INSUFFICIENT_BALANCE = 3002  # 余额不足
    ORDER_ERROR = 3003  # 订单错误
    PAYMENT_ERROR = 3004  # 支付错误
    QUOTA_EXCEEDED = 3005  # 配额超额


class ResponseType(Enum):
    """响应类型枚举"""

    SUCCESS = "success"  # 成功响应
    ERROR = "error"  # 错误响应
    WARNING = "warning"  # 警告响应
    INFO = "info"  # 信息响应


class StandardResponse(BaseModel):
    """标准API响应"""

    model_config = ConfigDict(json_encoders={Enum: lambda v: v.value})

    type: ResponseType
    code: int
    message: str
    data: Any | None = None
    timestamp: float
    request_id: str | None = None


class PaginatedResponse(BaseModel):
    """分页响应"""

    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class ErrorResponse(BaseModel):
    """错误响应"""

    type: ResponseType = ResponseType.ERROR
    code: int
    message: str
    details: dict[str, Any] | None = None
    timestamp: float
    request_id: str | None = None


class APISpec:
    """API规范类"""

    def __init__(self, app: FastAPI):
        self.app = app
        self._registered_routes = {}

    def register_route(
        self,
        path: str,
        methods: list[str],
        summary: str,
        description: str,
        response_model: type[BaseModel] = None,
        tags: list[str] = None,
    ):
        """注册API路由，记录API规范"""
        self._registered_routes[path] = {
            "methods": methods,
            "summary": summary,
            "description": description,
            "response_model": response_model,
            "tags": tags or [],
        }

    def generate_openapi(self) -> dict[str, Any]:
        """生成OpenAPI文档"""
        openapi_spec = self.app.openapi()

        # 添加自定义组件
        if "components" not in openapi_spec:
            openapi_spec["components"] = {}

        # 添加标准响应模型
        openapi_spec["components"]["schemas"]["StandardResponse"] = {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": [t.value for t in ResponseType]},
                "code": {"type": "integer"},
                "message": {"type": "string"},
                "data": {},
                "timestamp": {"type": "number", "format": "float"},
                "request_id": {"type": "string"},
            },
            "required": ["type", "code", "message", "timestamp"],
        }

        openapi_spec["components"]["schemas"]["ErrorResponse"] = {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["error"]},
                "code": {"type": "integer"},
                "message": {"type": "string"},
                "details": {"type": "object"},
                "timestamp": {"type": "number", "format": "float"},
                "request_id": {"type": "string"},
            },
            "required": ["type", "code", "message", "timestamp"],
        }

        openapi_spec["components"]["schemas"]["PaginatedResponse"] = {
            "type": "object",
            "properties": {
                "items": {"type": "array"},
                "total": {"type": "integer"},
                "page": {"type": "integer"},
                "page_size": {"type": "integer"},
                "total_pages": {"type": "integer"},
                "has_next": {"type": "boolean"},
                "has_prev": {"type": "boolean"},
            },
            "required": [
                "items",
                "total",
                "page",
                "page_size",
                "total_pages",
                "has_next",
                "has_prev",
            ],
        }

        return openapi_spec

    def generate_docs(self) -> str:
        """生成API文档"""
        openapi_spec = self.generate_openapi()
        return str(openapi_spec)


def create_success_response(
    data: Any = None,
    message: str = "Operation successful",
    code: int = ErrorCode.SUCCESS.value,
) -> StandardResponse:
    """创建成功响应"""
    return StandardResponse(
        type=ResponseType.SUCCESS,
        code=code,
        message=message,
        data=data,
        timestamp=time.time(),
    )


def create_error_response(
    error_code: ErrorCode,
    message: str = None,
    details: dict[str, Any] = None,
    request_id: str = None,
) -> ErrorResponse:
    """创建错误响应"""
    if message is None:
        message = error_code.name.replace("_", " ").title()

    return ErrorResponse(
        type=ResponseType.ERROR,
        code=error_code.value,
        message=message,
        details=details,
        timestamp=time.time(),
        request_id=request_id,
    )


def create_paginated_response(items: list[Any], total: int, page: int, page_size: int) -> PaginatedResponse:
    """创建分页响应"""
    total_pages = (total + page_size - 1) // page_size

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


class APIRouter:
    """标准API路由器"""

    def __init__(self, prefix: str = "", tags: list[str] = None):
        self.prefix = prefix
        self.tags = tags or []
        self.routes = {}

    def add_route(
        self,
        path: str,
        method: str,
        func,
        summary: str,
        description: str = "",
        response_model: type[BaseModel] = None,
        status_code: int = 200,
    ):
        """添加路由"""
        full_path = self.prefix + path
        self.routes[full_path] = {
            "method": method.upper(),
            "func": func,
            "summary": summary,
            "description": description,
            "response_model": response_model,
            "status_code": status_code,
            "tags": self.tags,
        }

    def include_router(self, app: FastAPI, api_spec: APISpec):
        """将路由注册到FastAPI应用"""
        for path, route_info in self.routes.items():
            method = route_info["method"]
            func = route_info["func"]
            summary = route_info["summary"]
            description = route_info["description"]
            response_model = route_info["response_model"]
            status_code = route_info["status_code"]
            tags = route_info["tags"]

            # 注册路由到API规范
            api_spec.register_route(
                path=path,
                methods=[method],
                summary=summary,
                description=description,
                response_model=response_model,
                tags=tags,
            )

            # 根据HTTP方法注册路由
            if method == "GET":
                app.get(
                    path,
                    summary=summary,
                    description=description,
                    response_model=response_model,
                    status_code=status_code,
                    tags=tags,
                )(func)
            elif method == "POST":
                app.post(
                    path,
                    summary=summary,
                    description=description,
                    response_model=response_model,
                    status_code=status_code,
                    tags=tags,
                )(func)
            elif method == "PUT":
                app.put(
                    path,
                    summary=summary,
                    description=description,
                    response_model=response_model,
                    status_code=status_code,
                    tags=tags,
                )(func)
            elif method == "DELETE":
                app.delete(
                    path,
                    summary=summary,
                    description=description,
                    response_model=response_model,
                    status_code=status_code,
                    tags=tags,
                )(func)
            elif method == "PATCH":
                app.patch(
                    path,
                    summary=summary,
                    description=description,
                    response_model=response_model,
                    status_code=status_code,
                    tags=tags,
                )(func)
