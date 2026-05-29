"""风险监控服务"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

task_logger = StructuredTaskLogger(logger, "RiskMonitor")


class RiskMonitor:
    """风险监控服务"""

    def __init__(self):
        self.default_config = {
            "max_drawdown_threshold": -0.20,  # 最大回撤阈值
            "var_threshold": -0.10,  # VaR 阈值
            "volatility_multiplier": 2.0,  # 波动率异常倍数
            "daily_loss_threshold": -0.05,  # 单日亏损阈值
            "consecutive_loss_days": 5,  # 连续亏损天数阈值
        }

    def calculate_risk_metrics(
        self,
        equity_curve: list[dict[str, Any]],
        benchmark_returns: list[float] | None = None,
    ) -> dict[str, float]:
        """
        计算风险指标

        Args:
            equity_curve: 权益曲线数据
            benchmark_returns: 基准收益率序列（可选）

        Returns:
            风险指标字典
        """
        if not equity_curve or len(equity_curve) < 2:
            return self._empty_metrics()

        try:
            df = pd.DataFrame(equity_curve)
            if "value" not in df.columns:
                return self._empty_metrics()

            # 计算收益率
            returns = df["value"].pct_change().dropna()

            if len(returns) == 0:
                return self._empty_metrics()

            # 计算各项指标
            metrics = {
                "var_95": self._calculate_var(returns, confidence=0.95),
                "var_99": self._calculate_var(returns, confidence=0.99),
                "cvar_95": self._calculate_cvar(returns, confidence=0.95),
                "max_drawdown": self._calculate_max_drawdown(df["value"]),
                "volatility": self._calculate_volatility(returns),
                "downside_volatility": self._calculate_downside_volatility(returns),
                "calmar_ratio": 0.0,  # 稍后计算
                "sortino_ratio": 0.0,  # 稍后计算
            }

            # 计算 Beta（如果有基准）
            if benchmark_returns and len(benchmark_returns) == len(returns):
                metrics["beta"] = self._calculate_beta(returns, benchmark_returns)
            else:
                metrics["beta"] = 0.0

            # 计算 Calmar Ratio
            annual_return = (df["value"].iloc[-1] / df["value"].iloc[0]) ** (252 / len(returns)) - 1
            if metrics["max_drawdown"] != 0:
                metrics["calmar_ratio"] = annual_return / abs(metrics["max_drawdown"])

            # 计算 Sortino Ratio
            if metrics["downside_volatility"] != 0:
                metrics["sortino_ratio"] = annual_return / metrics["downside_volatility"]

            return metrics

        except Exception as e:
            task_logger.error("calculate_risk_metrics_failed", "计算风险指标失败", error=str(e))
            return self._empty_metrics()

    def _calculate_var(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """计算 VaR（Value at Risk）"""
        return float(np.percentile(returns, (1 - confidence) * 100))

    def _calculate_cvar(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """计算 CVaR（Conditional VaR）"""
        var = self._calculate_var(returns, confidence)
        return float(returns[returns <= var].mean())

    def _calculate_max_drawdown(self, equity: pd.Series) -> float:
        """计算最大回撤"""
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        return float(drawdown.min())

    def _calculate_volatility(self, returns: pd.Series) -> float:
        """计算波动率（年化）"""
        return float(returns.std() * np.sqrt(252))

    def _calculate_downside_volatility(self, returns: pd.Series, target: float = 0.0) -> float:
        """计算下行波动率"""
        downside_returns = returns[returns < target]
        if len(downside_returns) == 0:
            return 0.0
        return float(downside_returns.std() * np.sqrt(252))

    def _calculate_beta(self, returns: pd.Series, benchmark_returns: list[float]) -> float:
        """计算 Beta"""
        try:
            benchmark_series = pd.Series(benchmark_returns)
            covariance = returns.cov(benchmark_series)
            benchmark_variance = benchmark_series.var()
            if benchmark_variance == 0:
                return 0.0
            return float(covariance / benchmark_variance)
        except Exception:
            return 0.0

    def _empty_metrics(self) -> dict[str, float]:
        """返回空指标"""
        return {
            "var_95": 0.0,
            "var_99": 0.0,
            "cvar_95": 0.0,
            "max_drawdown": 0.0,
            "volatility": 0.0,
            "beta": 0.0,
            "downside_volatility": 0.0,
            "calmar_ratio": 0.0,
            "sortino_ratio": 0.0,
        }

    def check_alerts(
        self, metrics: dict[str, float], config: dict[str, float] | None = None
    ) -> list[dict[str, Any]]:
        """
        检查风险预警

        Args:
            metrics: 风险指标
            config: 风险阈值配置

        Returns:
            预警列表
        """
        if config is None:
            config = self.default_config

        alerts = []

        # 检查最大回撤
        if metrics["max_drawdown"] < config["max_drawdown_threshold"]:
            alerts.append(
                {
                    "type": "max_drawdown",
                    "severity": "high",
                    "message": f"最大回撤达到 {metrics['max_drawdown']*100:.2f}%，超过阈值 {config['max_drawdown_threshold']*100:.2f}%",
                    "value": metrics["max_drawdown"],
                    "threshold": config["max_drawdown_threshold"],
                }
            )

        # 检查 VaR
        if metrics["var_95"] < config["var_threshold"]:
            alerts.append(
                {
                    "type": "var_95",
                    "severity": "medium",
                    "message": f"VaR(95%) 为 {metrics['var_95']*100:.2f}%，超过阈值 {config['var_threshold']*100:.2f}%",
                    "value": metrics["var_95"],
                    "threshold": config["var_threshold"],
                }
            )

        # 检查波动率（相对历史均值）
        # 这里简化处理，实际应该与历史波动率对比
        if metrics["volatility"] > 0.5:  # 年化波动率超过 50%
            alerts.append(
                {
                    "type": "volatility",
                    "severity": "medium",
                    "message": f"波动率达到 {metrics['volatility']*100:.2f}%，可能存在异常",
                    "value": metrics["volatility"],
                    "threshold": 0.5,
                }
            )

        return alerts

    def check_daily_alerts(
        self,
        equity_curve: list[dict[str, Any]],
        config: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """
        检查每日风险预警

        Args:
            equity_curve: 权益曲线数据
            config: 风险阈值配置

        Returns:
            预警列表
        """
        if config is None:
            config = self.default_config

        if not equity_curve or len(equity_curve) < 2:
            return []

        alerts = []

        try:
            df = pd.DataFrame(equity_curve)
            if "value" not in df.columns:
                return []

            # 计算每日收益率
            df["daily_return"] = df["value"].pct_change()

            # 检查单日亏损
            last_return = df["daily_return"].iloc[-1]
            if last_return < config["daily_loss_threshold"]:
                alerts.append(
                    {
                        "type": "daily_loss",
                        "severity": "high",
                        "message": f"单日亏损 {last_return*100:.2f}%，超过阈值 {config['daily_loss_threshold']*100:.2f}%",
                        "value": last_return,
                        "threshold": config["daily_loss_threshold"],
                    }
                )

            # 检查连续亏损天数
            consecutive_losses = 0
            for ret in reversed(df["daily_return"].dropna()):
                if ret < 0:
                    consecutive_losses += 1
                else:
                    break

            if consecutive_losses >= config["consecutive_loss_days"]:
                alerts.append(
                    {
                        "type": "consecutive_losses",
                        "severity": "high",
                        "message": f"连续亏损 {consecutive_losses} 天，超过阈值 {config['consecutive_loss_days']} 天",
                        "value": consecutive_losses,
                        "threshold": config["consecutive_loss_days"],
                    }
                )

        except Exception as e:
            task_logger.error("check_daily_alerts_failed", "检查每日预警失败", error=str(e))

        return alerts
