"""
性能监控服务
"""

import time
from collections import defaultdict, deque
from datetime import datetime
from typing import List, Optional

import psutil

from ..models.performance import (
    PerformanceAlert,
    PerformanceHistory,
    PerformanceQuery,
    ProviderPerformance,
    SystemPerformance,
)
from ..provider_registry import REGISTRY


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.request_stats = defaultdict(
            lambda: {
                "total": 0,
                "success": 0,
                "failed": 0,
                "response_times": deque(maxlen=100),
                "last_request": None,
            }
        )

        self.alert_thresholds = {
            "error_rate": 5.0,  # 错误率阈值（百分比）
            "response_time": 30000,  # 响应时间阈值（毫秒）
            "memory_usage": 80.0,  # 内存使用率阈值（百分比）
            "cpu_usage": 80.0,  # CPU使用率阈值（百分比）
            "success_rate": 95.0,  # 成功率阈值（百分比）
        }

        self.active_alerts = {}

    def record_request_start(self, provider_name: str, request_type: str = "generation"):
        """记录请求开始"""
        request_id = f"{provider_name}_{request_type}_{int(time.time() * 1000)}"
        self.request_stats[provider_name]["ongoing_requests"][request_id] = {
            "start_time": time.time(),
            "request_type": request_type,
        }
        return request_id

    def record_request_end(self, provider_name: str, request_id: str, success: bool, response_time: float):
        """记录请求结束"""
        stats = self.request_stats[provider_name]

        # 更新统计
        stats["total"] += 1
        if success:
            stats["success"] += 1
        else:
            stats["failed"] += 1

        stats["response_times"].append(response_time)
        stats["last_request"] = datetime.now()

        # 清理进行中的请求
        if "ongoing_requests" in stats and request_id in stats["ongoing_requests"]:
            del stats["ongoing_requests"][request_id]

        # 检查告警条件
        self._check_alerts(provider_name)

    def get_provider_performance(self, provider_name: str) -> ProviderPerformance:
        """获取Provider性能统计"""
        stats = self.request_stats.get(provider_name, {})

        if stats["total"] == 0:
            return ProviderPerformance(
                provider_name=provider_name,
                model_name=provider_name,
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                avg_response_time=0,
                min_response_time=0,
                max_response_time=0,
                success_rate=0.0,
                error_rate=100.0,
                last_request_time=datetime.now(),
                status="no_data",
            )

        response_times = list(stats["response_times"])
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = 0
            min_response_time = 0
            max_response_time = 0

        success_rate = (stats["success"] / stats["total"]) * 100
        error_rate = (stats["failed"] / stats["total"]) * 100

        return ProviderPerformance(
            provider_name=provider_name,
            model_name=provider_name,
            total_requests=stats["total"],
            successful_requests=stats["success"],
            failed_requests=stats["failed"],
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            success_rate=success_rate,
            error_rate=error_rate,
            last_request_time=stats["last_request"] or datetime.now(),
            status=("healthy" if success_rate >= 95 and avg_response_time < 30000 else "degraded"),
        )

    def get_system_performance(self) -> SystemPerformance:
        """获取系统性能统计"""
        total_requests = sum(stats["total"] for stats in self.request_stats.values())
        successful_requests = sum(stats["success"] for stats in self.request_stats.values())
        failed_requests = total_requests - successful_requests

        # 计算平均响应时间
        all_response_times = []
        for stats in self.request_stats.values():
            all_response_times.extend(stats["response_times"])

        avg_response_time = sum(all_response_times) / len(all_response_times) if all_response_times else 0

        # 获取系统资源使用情况
        try:
            memory_usage = psutil.virtual_memory().percent
            cpu_usage = psutil.cpu_percent(interval=1)
        except Exception:
            memory_usage = None
            cpu_usage = None

        return SystemPerformance(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response_time,
            active_providers=len(REGISTRY),
            memory_usage=memory_usage,
            cpu_usage=cpu_usage,
            uptime=int(time.time()),
            last_updated=datetime.now(),
        )

    def get_performance_history(self, query: PerformanceQuery) -> PerformanceHistory:
        """获取性能历史数据"""
        # 企业级金融业务禁止生成任何模拟/演示指标。
        # 当前版本未实现“从数据库/时序存储读取历史指标”，因此返回空数据。
        provider_name = query.provider_name or "all"
        time_range = query.time_range
        return PerformanceHistory(
            provider_name=provider_name,
            time_range=time_range,
            data_points=[],
            summary={},
        )

    def _check_alerts(self, provider_name: str):
        """检查告警条件"""
        stats = self.request_stats.get(provider_name, {})

        if stats["total"] == 0:
            return

        # 计算当前指标
        success_rate = (stats["success"] / stats["total"]) * 100
        error_rate = (stats["failed"] / stats["total"]) * 100

        response_times = list(stats["response_times"])
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        # 检查错误率告警
        if error_rate > self.alert_thresholds["error_rate"]:
            self._create_alert(
                "error_rate",
                "high",
                f"Provider {provider_name} 错误率过高: {error_rate:.1f}%",
                provider_name,
                "error_rate",
                error_rate,
                self.alert_thresholds["error_rate"],
            )

        # 检查响应时间告警
        if avg_response_time > self.alert_thresholds["response_time"]:
            self._create_alert(
                "response_time",
                "high",
                f"Provider {provider_name} 响应时间过长: {avg_response_time:.0f}ms",
                provider_name,
                "response_time",
                avg_response_time,
                self.alert_thresholds["response_time"],
            )

        # 检查成功率告警
        if success_rate < self.alert_thresholds["success_rate"]:
            self._create_alert(
                "success_rate",
                "low",
                f"Provider {provider_name} 成功率过低: {success_rate:.1f}%",
                provider_name,
                "success_rate",
                success_rate,
                self.alert_thresholds["success_rate"],
            )

        # 检查系统资源告警
        system_perf = self.get_system_performance()
        if system_perf.memory_usage and system_perf.memory_usage > self.alert_thresholds["memory_usage"]:
            self._create_alert(
                "memory_usage",
                "high",
                f"系统内存使用率过高: {system_perf.memory_usage:.1f}%",
                "system",
                "memory_usage",
                system_perf.memory_usage,
                self.alert_thresholds["memory_usage"],
            )

        if system_perf.cpu_usage and system_perf.cpu_usage > self.alert_thresholds["cpu_usage"]:
            self._create_alert(
                "cpu_usage",
                "high",
                f"系统CPU使用率过高: {system_perf.cpu_usage:.1f}%",
                "system",
                "cpu_usage",
                system_perf.cpu_usage,
                self.alert_thresholds["cpu_usage"],
            )

    def _create_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        provider_name: str,
        metric_name: str,
        current_value: float,
        threshold: float,
    ):
        """创建告警"""
        alert_id = f"{alert_type}_{provider_name}_{metric_name}_{int(time.time())}"

        alert = PerformanceAlert(
            id=alert_id,
            type=alert_type,
            severity=severity,
            message=message,
            provider_name=provider_name,
            metric_name=metric_name,
            current_value=current_value,
            threshold=threshold,
        )

        self.active_alerts[alert_id] = alert

    def resolve_alert(self, alert_id: str):
        """解决告警"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved_at = datetime.now()
            alert.status = "resolved"
            # 从活跃告警中移除
            del self.active_alerts[alert_id]

    def get_active_alerts(self) -> list[PerformanceAlert]:
        """获取活跃告警"""
        return list(self.active_alerts.values())

    def get_all_providers_performance(self) -> list[ProviderPerformance]:
        """获取所有Provider性能"""
        performances = []

        for provider_name in REGISTRY.keys():
            perf = self.get_provider_performance(provider_name)
            performances.append(perf)

        # 按成功率排序
        performances.sort(key=lambda x: x.success_rate, reverse=True)
        return performances

    def reset_stats(self, provider_name: str | None = None):
        """重置统计数据"""
        if provider_name:
            self.request_stats[provider_name] = {
                "total": 0,
                "success": 0,
                "failed": 0,
                "response_times": deque(maxlen=100),
                "last_request": None,
                "ongoing_requests": {},
            }
        else:
            self.request_stats.clear()


# 全局性能监控器实例
performance_monitor = PerformanceMonitor()
