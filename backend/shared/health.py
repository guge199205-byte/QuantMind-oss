#!/usr/bin/env python3
"""
QuantMind 统一健康检查模块

为所有微服务提供标准化的健康检查功能：
1. 基础健康检查
2. 数据库连接检查
3. 外部服务依赖检查
4. 性能指标检查
5. 服务状态汇总

Author: QuantMind Team
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List
from collections.abc import Callable


@dataclass
class HealthCheck:
    """单个健康检查项"""

    name: str
    status: str  # "healthy", "unhealthy", "degraded"
    message: str
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentHealth:
    """组件健康状态"""

    name: str
    status: str
    checks: list[HealthCheck] = field(default_factory=list)
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class HealthChecker:
    """健康检查器"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = logging.getLogger(f"{__name__}.{service_name}")
        self.checks: dict[str, Callable] = {}
        self.last_results: dict[str, ComponentHealth] = {}

    def register_check(self, name: str, check_func: Callable) -> None:
        """注册健康检查函数"""
        self.checks[name] = check_func
        self.logger.debug(f"Registered health check: {name}")

    async def run_check(self, name: str) -> HealthCheck:
        """运行单个健康检查"""
        if name not in self.checks:
            return HealthCheck(
                name=name,
                status="unhealthy",
                message=f"Health check '{name}' not found",
            )

        start_time = time.time()
        try:
            # 如果是协程函数，使用await
            if asyncio.iscoroutinefunction(self.checks[name]):
                result = await self.checks[name]()
            else:
                result = self.checks[name]()

            duration = (time.time() - start_time) * 1000

            if isinstance(result, str):
                return HealthCheck(name=name, status="healthy", message=result, duration_ms=duration)
            elif isinstance(result, dict):
                return HealthCheck(
                    name=name,
                    status=result.get("status", "healthy"),
                    message=result.get("message", "OK"),
                    duration_ms=duration,
                    details=result.get("details", {}),
                )
            else:
                return HealthCheck(name=name, status="healthy", message="OK", duration_ms=duration)

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            self.logger.error(f"Health check '{name}' failed: {e}")
            return HealthCheck(name=name, status="unhealthy", message=str(e), duration_ms=duration)

    async def check_all(self) -> dict[str, ComponentHealth]:
        """运行所有健康检查"""
        results = {}

        for name in self.checks:
            try:
                check_result = await self.run_check(name)

                # 更新或创建组件健康状态
                if name not in self.last_results:
                    self.last_results[name] = ComponentHealth(name=name, status="unknown")

                component = self.last_results[name]
                component.checks = [check_result]
                component.status = check_result.status
                component.last_check = datetime.now(timezone.utc)

                results[name] = component

            except Exception as e:
                self.logger.error(f"Failed to run health check '{name}': {e}")
                results[name] = ComponentHealth(
                    name=name,
                    status="unhealthy",
                    checks=[
                        HealthCheck(
                            name=name,
                            status="unhealthy",
                            message=f"Check execution failed: {e}",
                        )
                    ],
                )

        return results

    def get_overall_status(self, results: dict[str, ComponentHealth]) -> str:
        """获取整体健康状态"""
        if not results:
            return "unhealthy"

        statuses = [component.status for component in results.values()]

        if all(status == "healthy" for status in statuses):
            return "healthy"
        elif any(status == "unhealthy" for status in statuses):
            return "unhealthy"
        else:
            return "degraded"

    async def get_health_payload(self) -> dict[str, Any]:
        """获取完整的健康检查负载"""
        results = await self.check_all()
        overall_status = self.get_overall_status(results)

        return {
            "service": self.service_name,
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                name: {
                    "status": component.status,
                    "last_check": component.last_check.isoformat(),
                    "checks": [
                        {
                            "name": check.name,
                            "status": check.status,
                            "message": check.message,
                            "duration_ms": check.duration_ms,
                            "details": check.details,
                        }
                        for check in component.checks
                    ],
                }
                for name, component in results.items()
            },
        }


class StandardHealthChecks:
    """标准健康检查集合"""

    @staticmethod
    async def database_check(db_engine) -> HealthCheck:
        """数据库连接检查"""
        try:
            start_time = time.time()

            # 执行简单查询
            with db_engine.connect() as conn:
                result = conn.execute("SELECT 1").fetchone()

            duration = (time.time() - start_time) * 1000

            return HealthCheck(
                name="database",
                status="healthy",
                message="Database connection successful",
                duration_ms=duration,
                details={"query_result": str(result)},
            )
        except Exception as e:
            return HealthCheck(
                name="database",
                status="unhealthy",
                message=f"Database connection failed: {e}",
            )

    @staticmethod
    async def redis_check(redis_client) -> HealthCheck:
        """Redis连接检查"""
        try:
            start_time = time.time()

            # 执行ping测试
            result = redis_client.ping()
            duration = (time.time() - start_time) * 1000

            return HealthCheck(
                name="redis",
                status="healthy" if result else "unhealthy",
                message=("Redis connection successful" if result else "Redis ping failed"),
                duration_ms=duration,
                details={"ping_result": result},
            )
        except Exception as e:
            return HealthCheck(
                name="redis",
                status="unhealthy",
                message=f"Redis connection failed: {e}",
            )

    @staticmethod
    async def external_api_check(url: str, timeout: float = 5.0) -> HealthCheck:
        """外部API检查"""
        try:
            import httpx

            start_time = time.time()

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url)

            duration = (time.time() - start_time) * 1000

            if response.status_code < 400:
                return HealthCheck(
                    name="external_api",
                    status="healthy",
                    message=f"API check successful: {response.status_code}",
                    duration_ms=duration,
                    details={
                        "url": url,
                        "status_code": response.status_code,
                        "response_time_ms": duration,
                    },
                )
            else:
                return HealthCheck(
                    name="external_api",
                    status="degraded",
                    message=f"API returned error status: {response.status_code}",
                    duration_ms=duration,
                    details={"url": url, "status_code": response.status_code},
                )
        except Exception as e:
            return HealthCheck(
                name="external_api",
                status="unhealthy",
                message=f"API check failed: {e}",
                details={"url": url},
            )

    @staticmethod
    async def disk_space_check(path: str = ".", warning_threshold: float = 0.9) -> HealthCheck:
        """磁盘空间检查"""
        try:
            import shutil

            total, used, free = shutil.disk_usage(path)
            usage_ratio = used / total

            if usage_ratio >= warning_threshold:
                status = "degraded"
                message = f"Disk usage high: {usage_ratio:.1%}"
            else:
                status = "healthy"
                message = f"Disk usage normal: {usage_ratio:.1%}"

            return HealthCheck(
                name="disk_space",
                status=status,
                message=message,
                details={
                    "path": path,
                    "total_gb": total / (1024**3),
                    "used_gb": used / (1024**3),
                    "free_gb": free / (1024**3),
                    "usage_ratio": usage_ratio,
                },
            )
        except Exception as e:
            return HealthCheck(
                name="disk_space",
                status="unhealthy",
                message=f"Disk space check failed: {e}",
            )

    @staticmethod
    async def memory_check(warning_threshold: float = 0.9) -> HealthCheck:
        """内存使用检查"""
        try:
            import psutil

            memory = psutil.virtual_memory()
            usage_ratio = memory.percent / 100

            if usage_ratio >= warning_threshold:
                status = "degraded"
                message = f"Memory usage high: {memory.percent:.1f}%"
            else:
                status = "healthy"
                message = f"Memory usage normal: {memory.percent:.1f}%"

            return HealthCheck(
                name="memory",
                status=status,
                message=message,
                details={
                    "total_gb": memory.total / (1024**3),
                    "available_gb": memory.available / (1024**3),
                    "used_gb": memory.used / (1024**3),
                    "usage_percent": memory.percent,
                },
            )
        except Exception as e:
            return HealthCheck(name="memory", status="unhealthy", message=f"Memory check failed: {e}")


# 向后兼容的简化函数
def build_health_payload(service: str, extra: dict[str, Any] | None = None) -> dict:
    """构建基础健康检查负载（向后兼容）"""
    data = {"service": service, "ts": datetime.utcnow().isoformat() + "Z"}
    if extra:
        data.update(extra)
    return {"code": 0, "message": "ok", "data": data}


# 创建全局健康检查器实例
def create_health_checker(service_name: str) -> HealthChecker:
    """创建健康检查器实例"""
    return HealthChecker(service_name)


if __name__ == "__main__":
    # 测试健康检查功能
    async def test_health_checks():
        checker = HealthChecker("test_service")

        # 注册测试检查
        checker.register_check("test_check", lambda: {"status": "healthy", "message": "Test OK"})

        # 运行检查
        result = await checker.get_health_payload()
        print("Health check result:")
        import json

        print(json.dumps(result, indent=2, default=str))

    # 运行测试
    asyncio.run(test_health_checks())
