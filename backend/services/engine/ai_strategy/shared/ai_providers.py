from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class StrategyType(str, Enum):
    momentum = "momentum"
    mean_reversion = "mean_reversion"
    breakout = "breakout"
    factor = "factor"


class ComplexityLevel(str, Enum):
    simple = "simple"
    intermediate = "intermediate"
    advanced = "advanced"


class StrategyRequest(BaseModel):
    prompt: str = Field(..., description="策略描述")
    strategy_type: StrategyType | None = None
    complexity_level: ComplexityLevel = ComplexityLevel.intermediate
    target_assets: list[str] = Field(default_factory=list)
    timeframe: str = "1d"
    risk_tolerance: str = "medium"
    backtest_period: str = "2y"
    custom_requirements: list[str] = Field(default_factory=list)
