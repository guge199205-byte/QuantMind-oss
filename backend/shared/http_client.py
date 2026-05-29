#!/usr/bin/env python3
"""
统一HTTP客户端模块
提供统一的API调用功能，包括重试、超时、认证等功能
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin

import httpx

from .config import settings
from .observability.logging import LoggerMixin

logger = logging.getLogger(__name__)


class HttpMethod(str, Enum):
    """HTTP方法枚举"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ResponseStatus(str, Enum):
    """响应状态枚举"""

    SUCCESS = "success"
    CLIENT_ERROR = "client_error"
    SERVER_ERROR = "server_error"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"


@dataclass
class APIResponse:
    """API响应数据类"""

    status: ResponseStatus
    status_code: int
    data: Any | None = None
    headers: dict[str, str] | None = None
    error: str | None = None
    elapsed_time: float | None = None


@dataclass
class RequestConfig:
    """请求配置"""

    timeout: float = 30.0
    retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    validate_status: bool = True
    log_requests: bool = True
    log_responses: bool = False


class AuthProvider(ABC):
    """认证提供者抽象基类"""

    @abstractmethod
    def get_auth_headers(self) -> dict[str, str]:
        """获取认证头"""


class BearerTokenAuth(AuthProvider):
    """Bearer Token认证"""

    def __init__(self, token: str, header_name: str = "Authorization"):
        self.token = token
        self.header_name = header_name

    def get_auth_headers(self) -> dict[str, str]:
        return {self.header_name: f"Bearer {self.token}"}


class APIKeyAuth(AuthProvider):
    """API Key认证"""

    def __init__(self, api_key: str, header_name: str = "X-API-Key"):
        self.api_key = api_key
        self.header_name = header_name

    def get_auth_headers(self) -> dict[str, str]:
        return {self.header_name: self.api_key}


class CustomHeaderAuth(AuthProvider):
    """自定义头认证"""

    def __init__(self, headers: dict[str, str]):
        self.headers = headers

    def get_auth_headers(self) -> dict[str, str]:
        return self.headers.copy()


class HTTPClient(LoggerMixin):
    """统一HTTP客户端"""

    def __init__(
        self,
        base_url: str | None = None,
        config: RequestConfig | None = None,
        auth: AuthProvider | None = None,
        default_headers: dict[str, str] | None = None,
    ):
        """
        初始化HTTP客户端

        Args:
            base_url: 基础URL
            config: 请求配置
            auth: 认证提供者
            default_headers: 默认请求头
        """
        self.base_url = base_url or ""
        self.config = config or RequestConfig()
        self.auth = auth
        self.default_headers = default_headers or {}

        # 创建HTTP客户端
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )

        self.logger = self.get_logger()
        self._request_count = 0
        self._error_count = 0

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    def _build_url(self, endpoint: str) -> str:
        """构建完整URL"""
        if self.base_url:
            return urljoin(self.base_url, endpoint)
        return endpoint

    def _build_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        """构建请求头"""
        headers = self.default_headers.copy()

        if extra_headers:
            headers.update(extra_headers)

        if self.auth:
            auth_headers = self.auth.get_auth_headers()
            headers.update(auth_headers)

        return headers

    def _get_status_category(self, status_code: int) -> ResponseStatus:
        """获取响应状态分类"""
        if 200 <= status_code < 300:
            return ResponseStatus.SUCCESS
        elif 400 <= status_code < 500:
            return ResponseStatus.CLIENT_ERROR
        elif 500 <= status_code < 600:
            return ResponseStatus.SERVER_ERROR
        else:
            return ResponseStatus.NETWORK_ERROR

    async def _make_request(self, method: HttpMethod | str, endpoint: str, **kwargs) -> APIResponse:
        """执行HTTP请求"""
        method = HttpMethod(method) if isinstance(method, str) else method
        url = self._build_url(endpoint)
        headers = self._build_headers(kwargs.pop("headers", None))

        start_time = time.time()
        last_error = None

        # 记录请求
        if self.config.log_requests:
            self.logger.info(
                f"HTTP {method.value} {url}",
                extra={
                    "method": method.value,
                    "url": url,
                    "headers": dict(headers),
                    "params": kwargs.get("params"),
                    "has_body": "data" in kwargs or "json" in kwargs,
                },
            )

        # 重试逻辑
        for attempt in range(self.config.retries + 1):
            try:
                response = await self.client.request(method=method.value, url=url, headers=headers, **kwargs)

                elapsed_time = time.time() - start_time
                self._request_count += 1

                # 记录响应
                if self.config.log_responses:
                    self.logger.info(
                        f"HTTP Response {response.status_code} ({elapsed_time:.3f}s)",
                        extra={
                            "status_code": response.status_code,
                            "elapsed_time": elapsed_time,
                            "headers": dict(response.headers),
                            "response_size": len(response.content),
                        },
                    )

                # 构建响应对象
                api_response = APIResponse(
                    status=self._get_status_category(response.status_code),
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    elapsed_time=elapsed_time,
                )

                # 解析响应数据
                try:
                    content_type = response.headers.get("content-type", "").lower()
                    if "application/json" in content_type:
                        api_response.data = response.json()
                    else:
                        api_response.data = response.text
                except Exception as e:
                    self.logger.warning(f"Failed to parse response data: {e}")
                    api_response.data = response.text

                # 验证响应状态
                if self.config.validate_status and api_response.status != ResponseStatus.SUCCESS:
                    api_response.error = f"HTTP {response.status_code} error"
                    self._error_count += 1
                    self.logger.warning(
                        f"HTTP error: {response.status_code}",
                        extra={
                            "status_code": response.status_code,
                            "url": url,
                            "method": method.value,
                            "response_preview": (str(api_response.data)[:200] if api_response.data else None),
                        },
                    )

                return api_response

            except httpx.TimeoutException as e:
                last_error = e
                elapsed_time = time.time() - start_time
                self._error_count += 1

                if attempt < self.config.retries:
                    retry_delay = self.config.retry_delay * (self.config.retry_backoff**attempt)
                    self.logger.warning(
                        f"Request timeout, retrying in {retry_delay}s (attempt {attempt + 1}/{self.config.retries + 1})",
                        extra={
                            "url": url,
                            "method": method.value,
                            "timeout": self.config.timeout,
                            "attempt": attempt + 1,
                        },
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    self.logger.error(
                        f"Request timeout after {self.config.retries} retries",
                        extra={
                            "url": url,
                            "method": method.value,
                            "timeout": self.config.timeout,
                            "total_time": time.time() - start_time,
                        },
                    )
                    return APIResponse(
                        status=ResponseStatus.TIMEOUT,
                        status_code=0,
                        error=f"Request timeout after {self.config.retries} retries",
                        elapsed_time=time.time() - start_time,
                    )

            except httpx.NetworkError as e:
                last_error = e
                elapsed_time = time.time() - start_time
                self._error_count += 1

                if attempt < self.config.retries:
                    retry_delay = self.config.retry_delay * (self.config.retry_backoff**attempt)
                    self.logger.warning(
                        f"Network error, retrying in {retry_delay}s (attempt {attempt + 1}/{self.config.retries + 1})",
                        extra={
                            "url": url,
                            "method": method.value,
                            "error": str(e),
                            "attempt": attempt + 1,
                        },
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    self.logger.error(
                        f"Network error after {self.config.retries} retries: {e}",
                        extra={
                            "url": url,
                            "method": method.value,
                            "error": str(e),
                            "total_time": time.time() - start_time,
                        },
                    )
                    return APIResponse(
                        status=ResponseStatus.NETWORK_ERROR,
                        status_code=0,
                        error=f"Network error: {e}",
                        elapsed_time=time.time() - start_time,
                    )

            except Exception as e:
                last_error = e
                elapsed_time = time.time() - start_time
                self._error_count += 1
                self.logger.error(
                    f"Unexpected error during request: {e}",
                    extra={
                        "url": url,
                        "method": method.value,
                        "error": str(e),
                        "total_time": time.time() - start_time,
                    },
                )
                return APIResponse(
                    status=ResponseStatus.NETWORK_ERROR,
                    status_code=0,
                    error=f"Unexpected error: {e}",
                    elapsed_time=time.time() - start_time,
                )

        # 如果所有重试都失败
        self.logger.error(f"All {self.config.retries + 1} attempts failed")
        return APIResponse(
            status=ResponseStatus.NETWORK_ERROR,
            status_code=0,
            error=f"All retries failed: {last_error}",
            elapsed_time=time.time() - start_time,
        )

    # 便捷方法
    async def get(self, endpoint: str, params: dict | None = None, **kwargs) -> APIResponse:
        """GET请求"""
        return await self._make_request(HttpMethod.GET, endpoint, params=params, **kwargs)

    async def post(self, endpoint: str, data: Any = None, json: Any = None, **kwargs) -> APIResponse:
        """POST请求"""
        return await self._make_request(HttpMethod.POST, endpoint, data=data, json=json, **kwargs)

    async def put(self, endpoint: str, data: Any = None, json: Any = None, **kwargs) -> APIResponse:
        """PUT请求"""
        return await self._make_request(HttpMethod.PUT, endpoint, data=data, json=json, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> APIResponse:
        """DELETE请求"""
        return await self._make_request(HttpMethod.DELETE, endpoint, **kwargs)

    async def patch(self, endpoint: str, data: Any = None, json: Any = None, **kwargs) -> APIResponse:
        """PATCH请求"""
        return await self._make_request(HttpMethod.PATCH, endpoint, data=data, json=json, **kwargs)

    def get_stats(self) -> dict[str, Any]:
        """获取客户端统计信息"""
        return {
            "total_requests": self._request_count,
            "total_errors": self._error_count,
            "error_rate": self._error_count / max(self._request_count, 1),
            "success_rate": (self._request_count - self._error_count) / max(self._request_count, 1),
        }


class ServiceClient(HTTPClient):
    """服务客户端基类"""

    def __init__(
        self,
        service_name: str,
        config: RequestConfig | None = None,
        auth: AuthProvider | None = None,
    ):
        """
        初始化服务客户端

        Args:
            service_name: 服务名称
            config: 请求配置
            auth: 认证提供者
        """
        # 从统一配置获取服务URL
        service_port = settings.get_service_port(service_name)
        base_url = f"http://localhost:{service_port}"

        # 设置默认头部
        default_headers = {
            "User-Agent": f"QuantMind-{service_name}-Client/1.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        super().__init__(base_url=base_url, config=config, auth=auth, default_headers=default_headers)

        self.service_name = service_name

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            response = await self.get("/health")
            return response.status == ResponseStatus.SUCCESS
        except Exception as e:
            self.logger.error(f"Health check failed for {self.service_name}: {e}")
            return False

    async def get_service_info(self) -> dict[str, Any]:
        """获取服务信息"""
        response = await self.get("/")
        if response.status == ResponseStatus.SUCCESS:
            return response.data
        else:
            return {"error": response.error, "status": response.status}


# 预定义的服务客户端
class AIClient(ServiceClient):
    """AI策略服务客户端"""

    def __init__(self, api_key: str | None = None):
        auth = None
        if api_key:
            auth = BearerTokenAuth(api_key)

        super().__init__(service_name="ai_strategy", auth=auth)

    async def generate_strategy(self, description: str, **kwargs) -> APIResponse:
        """生成策略"""
        return await self.post("/api/v1/strategy/generate", json={"description": description, **kwargs})


class MarketDataClient(ServiceClient):
    """市场数据服务客户端"""

    def __init__(self):
        super().__init__(service_name="market_data")

    async def get_indices(self) -> APIResponse:
        """获取指数数据"""
        return await self.get("/api/v1/market/indices")

    async def get_market_overview(self) -> APIResponse:
        """获取市场概览"""
        return await self.get("/api/v1/market/overview")


class TradingClient(ServiceClient):
    """交易服务客户端"""

    def __init__(self):
        super().__init__(service_name="trading")


# 客户端工厂
class ClientFactory:
    """客户端工厂"""

    @staticmethod
    def create_ai_client(api_key: str | None = None) -> AIClient:
        """创建AI客户端"""
        return AIClient(api_key)

    @staticmethod
    def create_market_data_client() -> MarketDataClient:
        """创建市场数据客户端"""
        return MarketDataClient()

    @staticmethod
    def create_trading_client() -> TradingClient:
        """创建交易客户端"""
        return TradingClient()

    @staticmethod
    def create_service_client(service_name: str, **kwargs) -> ServiceClient:
        """创建通用服务客户端"""
        return ServiceClient(service_name, **kwargs)


# 全局客户端实例（已弃用，建议使用ClientFactory）
_ai_client: AIClient | None = None
_market_data_client: MarketDataClient | None = None
_trading_client: TradingClient | None = None


def get_ai_client(api_key: str | None = None) -> AIClient:
    """获取AI客户端（已弃用，建议使用ClientFactory.create_ai_client）"""
    global _ai_client
    if _ai_client is None:
        _ai_client = ClientFactory.create_ai_client(api_key)
    return _ai_client


def get_market_data_client() -> MarketDataClient:
    """获取市场数据客户端（已弃用，建议使用ClientFactory.create_market_data_client）"""
    global _market_data_client
    if _market_data_client is None:
        _market_data_client = ClientFactory.create_market_data_client()
    return _market_data_client


def get_trading_client() -> TradingClient:
    """获取交易客户端（已弃用，建议使用ClientFactory.create_trading_client）"""
    global _trading_client
    if _trading_client is None:
        _trading_client = ClientFactory.create_trading_client()
    return _trading_client
