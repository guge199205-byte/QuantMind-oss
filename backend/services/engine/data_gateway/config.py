"""Data Gateway 配置"""

import os

# 服务配置
SERVICE_HOST = os.getenv("DATA_GATEWAY_HOST", "0.0.0.0")
SERVICE_PORT = int(os.getenv("DATA_GATEWAY_PORT", "8004"))

# Tushare Token（可选）
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

# 默认数据源
DEFAULT_PROVIDER = os.getenv("DEFAULT_DATA_PROVIDER", "akshare")

# 支持的数据源
SUPPORTED_PROVIDERS = ["akshare", "eastmoney", "tushare"]
