"""
Data Gateway - 多数据源金融数据网关服务
端口: 8004
"""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("data-gateway")

app = FastAPI(
    title="QuantMind Data Gateway",
    description="多数据源金融数据网关 (akshare/eastmoney)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from backend.services.engine.data_gateway.routers.market import router as market_router
from backend.services.engine.data_gateway.routers.technical import router as technical_router

app.include_router(market_router)
app.include_router(technical_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "data-gateway"}


@app.get("/")
async def root():
    return {
        "service": "QuantMind Data Gateway",
        "version": "0.1.0",
        "endpoints": {
            "market": "/api/v1/market/",
            "technical": "/api/v1/technical/",
            "docs": "/docs",
        },
    }


if __name__ == "__main__":
    import uvicorn
    from backend.services.engine.data_gateway.config import SERVICE_HOST, SERVICE_PORT

    uvicorn.run(app, host=SERVICE_HOST, port=SERVICE_PORT)
