"""Portfolio module configuration for quantmind-trade."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "Portfolio Module"
    APP_VERSION: str = "2.0.0"

    # Remote service URLs
    STRATEGY_SERVICE_URL: str = os.getenv("STRATEGY_SERVICE_URL", "http://quantmind-engine:8001")
    REAL_TRADING_SERVICE_URL: str = os.getenv("REAL_TRADING_SERVICE_URL", "http://quantmind-trade:8002")

    # Cache TTL
    CACHE_TTL_PORTFOLIO: int = 300
    CACHE_TTL_POSITION: int = 60
    CACHE_TTL_PERFORMANCE: int = 180

    # Business limits
    MAX_PORTFOLIOS_PER_USER: int = 50
    MAX_POSITIONS_PER_PORTFOLIO: int = 200


settings = Settings()
