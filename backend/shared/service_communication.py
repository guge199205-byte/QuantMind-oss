#!/usr/bin/env python3
"""
服务间通信标准化模块
提供统一的服务通信接口、消息格式、错误处理等功能
"""

import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .http_client import ClientFactory, HTTPClient, ResponseStatus

logger = logging.getLogger(__name__)


class MessageFormat(str, Enum):
    """消息格式枚举"""

    JSON = "json"
    PROTOBUF = "protobu"
    XML = "xml"


class CommunicationProtocol(str, Enum):
    """通信协议枚举"""

    HTTP = "http"
    GRPC = "grpc"
    WEBSOCKET = "websocket"
    MESSAGE_QUEUE = "message_queue"


class Priority(str, Enum):
    """消息优先级"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ServiceMessage:
    """服务消息"""

    message_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time.time)
    source_service: str = ""
    target_service: str = ""
    message_type: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    format: MessageFormat = MessageFormat.JSON
    protocol: CommunicationProtocol = CommunicationProtocol.HTTP
    correlation_id: str | None = None
    reply_to: str | None = None
    expires_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "source_service": self.source_service,
            "target_service": self.target_service,
            "message_type": self.message_type,
            "data": self.data,
            "metadata": self.metadata,
            "priority": self.priority,
            "format": self.format,
            "protocol": self.protocol,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServiceMessage":
        """从字典创建消息"""
        return cls(**data)

    def is_expired(self) -> bool:
        """检查消息是否过期"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


@dataclass
class ServiceResponse:
    """服务响应"""

    message_id: str
    status: str
    data: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    processing_time: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "message_id": self.message_id,
            "status": self.status,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "processing_time": self.processing_time,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServiceResponse":
        """从字典创建响应"""
        return cls(**data)

    def is_success(self) -> bool:
        """检查是否成功"""
        return self.status == "success"

    def is_error(self) -> bool:
        """检查是否错误"""
        return self.status == "error"


class ServiceCommunicator(ABC):
    """服务通信器抽象基类"""

    @abstractmethod
    async def send_message(self, message: ServiceMessage) -> ServiceResponse:
        """发送消息"""

    @abstractmethod
    async def send_request(self, service_name: str, endpoint: str, data: dict[str, Any]) -> ServiceResponse:
        """发送请求"""

    @abstractmethod
    async def broadcast_message(self, message: ServiceMessage, services: list[str]) -> list[ServiceResponse]:
        """广播消息"""


class HTTPServiceCommunicator(ServiceCommunicator):
    """HTTP服务通信器"""

    def __init__(self, source_service: str, timeout: int = 30):
        self.source_service = source_service
        self.timeout = timeout
        self._client_manager = {}

    def _get_client(self, service_name: str) -> HTTPClient:
        """获取HTTP客户端"""
        if service_name not in self._client_manager:
            client = ClientFactory.create_service_client(service_name)
            self._client_manager[service_name] = client
        return self._client_manager[service_name]

    async def send_message(self, message: ServiceMessage) -> ServiceResponse:
        """发送消息"""
        if message.is_expired():
            return ServiceResponse(message_id=message.message_id, status="error", error="Message expired")

        client = self._get_client(message.target_service)
        start_time = time.time()

        try:
            # 构建请求URL
            endpoint = f"/api/v2/messages/{message.message_type}"

            # 发送请求
            response = await client.post(endpoint, json=message.to_dict())

            processing_time = time.time() - start_time

            if response.status == ResponseStatus.SUCCESS:
                return ServiceResponse(
                    message_id=message.message_id,
                    status="success",
                    data=response.data,
                    processing_time=processing_time,
                )
            else:
                return ServiceResponse(
                    message_id=message.message_id,
                    status="error",
                    error=response.error or "Request failed",
                    processing_time=processing_time,
                )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"HTTP消息发送失败: {e}")
            return ServiceResponse(
                message_id=message.message_id,
                status="error",
                error=str(e),
                processing_time=processing_time,
            )

    async def send_request(self, service_name: str, endpoint: str, data: dict[str, Any]) -> ServiceResponse:
        """发送请求"""
        message = ServiceMessage(
            source_service=self.source_service,
            target_service=service_name,
            message_type="request",
            data=data,
        )

        # 临时修改消息以支持特定端点
        original_type = message.message_type
        message.message_type = endpoint.strip("/")

        response = await self.send_message(message)

        # 恢复原始消息类型
        message.message_type = original_type

        return response

    async def broadcast_message(self, message: ServiceMessage, services: list[str]) -> list[ServiceResponse]:
        """广播消息"""
        tasks = []
        for service_name in services:
            service_message = ServiceMessage(
                source_service=message.source_service,
                target_service=service_name,
                message_type=message.message_type,
                data=message.data,
                metadata=message.metadata,
                priority=message.priority,
            )
            tasks.append(self.send_message(service_message))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常结果
        result = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                result.append(
                    ServiceResponse(
                        message_id=message.message_id,
                        status="error",
                        error=str(response),
                    )
                )
            else:
                result.append(response)

        return result


class MessageQueueCommunicator(ServiceCommunicator):
    """消息队列通信器"""

    def __init__(
        self,
        source_service: str,
        queue_url: str = "",
    ):
        self.source_service = source_service
        self.queue_url = queue_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._queue = None  # 这里应该初始化Redis或其他消息队列

    async def send_message(self, message: ServiceMessage) -> ServiceResponse:
        """发送消息到队列"""
        # 这里实现消息队列发送逻辑
        # 暂时返回成功响应
        return ServiceResponse(
            message_id=message.message_id,
            status="success",
            data={"queue": "message_queued"},
        )

    async def send_request(self, service_name: str, endpoint: str, data: dict[str, Any]) -> ServiceResponse:
        """发送请求到队列"""
        message = ServiceMessage(
            source_service=self.source_service,
            target_service=service_name,
            message_type=endpoint,
            data=data,
        )
        return await self.send_message(message)

    async def broadcast_message(self, message: ServiceMessage, services: list[str]) -> list[ServiceResponse]:
        """广播消息到队列"""
        responses = []
        for service_name in services:
            service_message = ServiceMessage(
                source_service=message.source_service,
                target_service=service_name,
                message_type=message.message_type,
                data=message.data,
            )
            response = await self.send_message(service_message)
            responses.append(response)
        return responses


class ServiceCommunicationManager:
    """服务通信管理器"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._communicators: dict[CommunicationProtocol, ServiceCommunicator] = {}
        self._message_handlers: dict[str, callable] = {}
        self._message_history: list[ServiceMessage] = []
        self._max_history = 1000

        # 初始化通信器
        self._initialize_communicators()

    def _initialize_communicators(self):
        """初始化通信器"""
        self._communicators[CommunicationProtocol.HTTP] = HTTPServiceCommunicator(self.service_name)
        self._communicators[CommunicationProtocol.MESSAGE_QUEUE] = MessageQueueCommunicator(self.service_name)

    def register_message_handler(self, message_type: str, handler: callable):
        """注册消息处理器"""
        self._message_handlers[message_type] = handler
        logger.info(f"注册消息处理器: {message_type}")

    def get_communicator(self, protocol: CommunicationProtocol) -> ServiceCommunicator:
        """获取通信器"""
        return self._communicators.get(protocol)

    async def send_message(self, message: ServiceMessage) -> ServiceResponse:
        """发送消息"""
        # 记录消息历史
        self._add_to_history(message)

        # 获取对应的通信器
        communicator = self.get_communicator(message.protocol)
        if not communicator:
            return ServiceResponse(
                message_id=message.message_id,
                status="error",
                error=f"Unsupported protocol: {message.protocol}",
            )

        try:
            return await communicator.send_message(message)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return ServiceResponse(message_id=message.message_id, status="error", error=str(e))

    async def send_request(
        self,
        service_name: str,
        endpoint: str,
        data: dict[str, Any],
        protocol: CommunicationProtocol = CommunicationProtocol.HTTP,
    ) -> ServiceResponse:
        """发送请求"""
        communicator = self.get_communicator(protocol)
        if not communicator:
            return ServiceResponse(message_id="", status="error", error=f"Unsupported protocol: {protocol}")

        return await communicator.send_request(service_name, endpoint, data)

    async def broadcast_message(
        self,
        message: ServiceMessage,
        services: list[str],
        protocol: CommunicationProtocol = CommunicationProtocol.HTTP,
    ) -> list[ServiceResponse]:
        """广播消息"""
        communicator = self.get_communicator(protocol)
        if not communicator:
            return [
                ServiceResponse(
                    message_id=message.message_id,
                    status="error",
                    error=f"Unsupported protocol: {protocol}",
                )
            ]

        return await communicator.broadcast_message(message, services)

    async def handle_message(self, message: ServiceMessage) -> ServiceResponse:
        """处理接收到的消息"""
        # 检查消息是否过期
        if message.is_expired():
            return ServiceResponse(message_id=message.message_id, status="error", error="Message expired")

        # 查找消息处理器
        handler = self._message_handlers.get(message.message_type)
        if not handler:
            return ServiceResponse(
                message_id=message.message_id,
                status="error",
                error=f"No handler for message type: {message.message_type}",
            )

        try:
            # 调用处理器
            result = await handler(message)
            if isinstance(result, ServiceResponse):
                return result
            else:
                return ServiceResponse(
                    message_id=message.message_id,
                    status="success",
                    data={"result": result},
                )
        except Exception as e:
            logger.error(f"消息处理失败: {e}")
            return ServiceResponse(message_id=message.message_id, status="error", error=str(e))

    def _add_to_history(self, message: ServiceMessage):
        """添加到消息历史"""
        self._message_history.append(message)
        if len(self._message_history) > self._max_history:
            self._message_history.pop(0)

    def get_message_history(self, limit: int = 100) -> list[ServiceMessage]:
        """获取消息历史"""
        return self._message_history[-limit:]

    def get_communication_stats(self) -> dict[str, Any]:
        """获取通信统计"""
        return {
            "service_name": self.service_name,
            "supported_protocols": list(self._communicators.keys()),
            "registered_handlers": len(self._message_handlers),
            "message_history_size": len(self._message_history),
            "handlers": list(self._message_handlers.keys()),
        }


# 全局通信管理器实例
_communication_managers: dict[str, ServiceCommunicationManager] = {}


def get_communication_manager(service_name: str) -> ServiceCommunicationManager:
    """获取通信管理器实例"""
    if service_name not in _communication_managers:
        _communication_managers[service_name] = ServiceCommunicationManager(service_name)
    return _communication_managers[service_name]


# 标准消息类型定义
class StandardMessageTypes:
    """标准消息类型"""

    # 用户相关
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"

    # 策略相关
    STRATEGY_CREATED = "strategy.created"
    STRATEGY_UPDATED = "strategy.updated"
    STRATEGY_DELETED = "strategy.deleted"
    STRATEGY_EXECUTED = "strategy.executed"
    STRATEGY_BACKTEST_STARTED = "strategy.backtest_started"
    STRATEGY_BACKTEST_COMPLETED = "strategy.backtest_completed"

    # 市场数据相关
    MARKET_DATA_UPDATED = "market.data_updated"
    MARKET_ALERT = "market.alert"
    PRICE_CHANGE = "market.price_change"

    # 系统相关
    SYSTEM_HEALTH_CHECK = "system.health_check"
    SYSTEM_METRICS = "system.metrics"
    SYSTEM_ALERT = "system.alert"

    # 服务间通信
    SERVICE_DISCOVERY = "service.discovery"
    SERVICE_REGISTERED = "service.registered"
    SERVICE_UNREGISTERED = "service.unregistered"
    SERVICE_HEALTH_UPDATE = "service.health_update"


class StandardErrorCodes:
    """标准错误码"""

    # 通用错误
    SUCCESS = "success"
    UNKNOWN_ERROR = "unknown_error"
    INVALID_REQUEST = "invalid_request"
    PERMISSION_DENIED = "permission_denied"
    RESOURCE_NOT_FOUND = "resource_not_found"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

    # 服务相关错误
    SERVICE_UNAVAILABLE = "service_unavailable"
    SERVICE_TIMEOUT = "service_timeout"
    SERVICE_ERROR = "service_error"

    # 数据相关错误
    DATA_VALIDATION_ERROR = "data_validation_error"
    DATA_CONFLICT = "data_conflict"
    DATA_CORRUPTION = "data_corruption"

    # 业务逻辑错误
    BUSINESS_RULE_VIOLATION = "business_rule_violation"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    QUOTA_EXCEEDED = "quota_exceeded"


def create_standard_message(
    message_type: str,
    source_service: str,
    target_service: str,
    data: dict[str, Any],
    **kwargs,
) -> ServiceMessage:
    """创建标准消息"""
    return ServiceMessage(
        source_service=source_service,
        target_service=target_service,
        message_type=message_type,
        data=data,
        **kwargs,
    )


def create_success_response(message_id: str, data: dict[str, Any] = None) -> ServiceResponse:
    """创建成功响应"""
    return ServiceResponse(message_id=message_id, status="success", data=data or {})


def create_error_response(
    message_id: str,
    error_code: str,
    error_message: str,
    metadata: dict[str, Any] = None,
) -> ServiceResponse:
    """创建错误响应"""
    return ServiceResponse(
        message_id=message_id,
        status="error",
        error=f"{error_code}: {error_message}",
        metadata=metadata or {"error_code": error_code},
    )
