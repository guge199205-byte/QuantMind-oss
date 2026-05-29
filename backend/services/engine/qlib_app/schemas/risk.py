"""风险监控 Schema"""

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class RiskMetrics(BaseModel):
    """风险指标"""

    var_95: float = Field(..., description="VaR (95% 置信度)")
    var_99: float = Field(..., description="VaR (99% 置信度)")
    cvar_95: float = Field(..., description="CVaR (95% 置信度)")
    max_drawdown: float = Field(..., description="最大回撤")
    volatility: float = Field(..., description="波动率（年化）")
    beta: float = Field(..., description="Beta 值")
    downside_volatility: float = Field(..., description="下行波动率")
    calmar_ratio: float = Field(..., description="卡尔玛比率")
    sortino_ratio: float = Field(..., description="索提诺比率")


class RiskAlert(BaseModel):
    """风险预警"""

    type: str = Field(..., description="预警类型")
    severity: str = Field(..., description="严重程度: low/medium/high")
    message: str = Field(..., description="预警消息")
    value: float = Field(..., description="当前值")
    threshold: float = Field(..., description="阈值")
    timestamp: datetime = Field(default_factory=datetime.now, description="预警时间")


class RiskConfig(BaseModel):
    """风险配置"""

    max_drawdown_threshold: float = Field(-0.20, description="最大回撤阈值")
    var_threshold: float = Field(-0.10, description="VaR 阈值")
    volatility_multiplier: float = Field(2.0, description="波动率异常倍数")
    daily_loss_threshold: float = Field(-0.05, description="单日亏损阈值")
    consecutive_loss_days: int = Field(5, description="连续亏损天数阈值")


class RiskMonitorResponse(BaseModel):
    """风险监控响应"""

    backtest_id: str
    metrics: RiskMetrics
    alerts: list[RiskAlert]
    config: RiskConfig
    updated_at: datetime = Field(default_factory=datetime.now)
