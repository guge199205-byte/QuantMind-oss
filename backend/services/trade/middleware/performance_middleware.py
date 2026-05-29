"""
性能监控中间件
用于监控和优化API响应时间
"""

import logging
import time
from functools import wraps
from collections.abc import Callable

from flask import g, request

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.metrics = {
            "requests": 0,
            "total_time": 0,
            "slow_requests": 0,
            "endpoints": {},
        }
        self.slow_threshold = 1.0  # 慢请求阈值：1秒

    def record_request(self, endpoint: str, method: str, duration: float):
        """
        记录请求性能指标

        Args:
            endpoint: API端点
            method: HTTP方法
            duration: 请求耗时（秒）
        """
        self.metrics["requests"] += 1
        self.metrics["total_time"] += duration

        if duration > self.slow_threshold:
            self.metrics["slow_requests"] += 1
            logger.warning(f"慢请求: {method} {endpoint} - {duration:.3f}s")

            # 记录端点级别的指标
        key = f"{method} {endpoint}"
        if key not in self.metrics["endpoints"]:
            self.metrics["endpoints"][key] = {
                "count": 0,
                "total_time": 0,
                "min_time": float("in"),
                "max_time": 0,
            }

        endpoint_metrics = self.metrics["endpoints"][key]
        endpoint_metrics["count"] += 1
        endpoint_metrics["total_time"] += duration
        endpoint_metrics["min_time"] = min(endpoint_metrics["min_time"], duration)
        endpoint_metrics["max_time"] = max(endpoint_metrics["max_time"], duration)

    def get_stats(self) -> dict:
        """获取性能统计信息"""
        if self.metrics["requests"] == 0:
            return {"requests": 0, "avg_time": 0, "slow_requests": 0, "endpoints": {}}

            # 计算端点平均响应时间
        endpoints_stats = {}
        for key, metrics in self.metrics["endpoints"].items():
            endpoints_stats[key] = {
                "count": metrics["count"],
                "avg_time": metrics["total_time"] / metrics["count"],
                "min_time": metrics["min_time"],
                "max_time": metrics["max_time"],
            }

        return {
            "requests": self.metrics["requests"],
            "avg_time": self.metrics["total_time"] / self.metrics["requests"],
            "slow_requests": self.metrics["slow_requests"],
            "slow_rate": self.metrics["slow_requests"] / self.metrics["requests"],
            "endpoints": endpoints_stats,
        }

    def reset(self):
        """重置统计指标"""
        self.metrics = {
            "requests": 0,
            "total_time": 0,
            "slow_requests": 0,
            "endpoints": {},
        }

        # 全局性能监控器实例


_monitor = PerformanceMonitor()


def performance_middleware(app):
    """
    Flask性能监控中间件

    Args:
        app: Flask应用实例
    """

    @app.before_request
    def before_request():
        """请求开始时记录时间"""
        g.start_time = time.time()

    @app.after_request
    def after_request(response):
        """请求结束时计算耗时"""
        if hasattr(g, "start_time"):
            duration = time.time() - g.start_time
            endpoint = request.endpoint or request.path
            method = request.method

            # 记录性能指标
            _monitor.record_request(endpoint, method, duration)

            # 添加响应头
            response.headers["X-Response-Time"] = f"{duration:.3f}s"

            # 记录慢请求详情
            if duration > _monitor.slow_threshold:
                logger.warning(
                    f"慢请求详情: {method} {request.path} "
                    f"[{duration:.3f}s] "
                    f"参数: {request.args.to_dict()} "
                    f"状态: {response.status_code}"
                )

        return response


def performance_decorator(threshold: float = 1.0):
    """
    性能监控装饰器
    用于监控特定函数的执行时间

    Args:
        threshold: 慢执行阈值（秒）

    Usage:
        @performance_decorator(threshold=0.5)
        def slow_function():
            # 耗时操作
            pass
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            if duration > threshold:
                logger.warning(f"慢函数: {func.__name__} " f"执行时间: {duration:.3f}s " f"(阈值: {threshold}s)")
            else:
                logger.debug(f"函数 {func.__name__} " f"执行时间: {duration:.3f}s")

            return result

        return wrapper

    return decorator


def get_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    return _monitor
