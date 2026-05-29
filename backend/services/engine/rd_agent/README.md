# RD-Agent 多市场因子挖掘框架

## 概述

本模块将 Microsoft [RD-Agent](https://github.com/microsoft/RD-Agent) 集成到 QuantMind，提供可扩展的多市场因子挖掘能力。通过 `MarketAdapter` 模式，每个市场只需实现一个适配器类即可接入。

## 架构

```
backend/services/engine/rd_agent/
├── __init__.py                    # 包入口
├── rd_loop_wrapper.py             # RDLoop 封装器（核心桥接层）
├── market_adapters/               # 市场适配器
│   ├── __init__.py                # 注册表 (@register_adapter)
│   ├── base.py                    # MarketAdapter 基类
│   ├── a_share.py                 # A股适配器
│   ├── crypto.py                  # 加密货币适配器 (Binance)
│   ├── hong_kong.py               # 港股适配器（预留）
│   └── us_stock.py                # 美股适配器（预留）
└── data_pipeline/                 # 数据管线
    └── crypto_data.py             # 加密货币数据下载 (Binance API → H5 → Qlib)
```

## 数据流

```
用户选择市场 → ChatInput (前端市场按钮)
  → POST /api/v1/alpha-agent/evolve?market=crypto&direction=...
    → launcher.start_evolution(market="crypto")
      → get_adapter("crypto").get_env_overrides()
      → subprocess: run_rd_agent.py --market crypto
        → RDLoopWrapper("crypto").run()
          → FactorRDLoop(FactorBasePropSetting)
            → RDLoop 步骤: propose → exp_gen → coding → running → feedback → record
```

## 市场适配器 (MarketAdapter)

### 接口

```python
class MarketAdapter(ABC):
    market_id: str           # "a_share", "crypto", "hong_kong", "us_stock"
    market_name: str         # "A股", "加密货币", "港股", "美股"
    description: str         # 市场描述

    def get_data_config(self) -> DataConfig          # 数据管线配置
    def get_qlib_provider_uri(self) -> str           # Qlib 数据目录
    def get_backtest_config(self) -> BacktestConfig  # 回测参数
    def get_factor_set(self) -> dict[str, str]       # 因子集 (name → expression)
    def get_prop_setting_class(self) -> str          # RD-Agent PropSetting 类路径
    def get_env_overrides(self) -> dict[str, str]    # 子进程环境变量
    def prepare_data(self) -> bool                   # 数据准备（下载/转换）
    def is_data_ready(self) -> bool                  # 数据就绪检查
```

### 添加新市场

1. 创建 `market_adapters/new_market.py`:

```python
from . import register_adapter
from .base import BacktestConfig, DataConfig, MarketAdapter

@register_adapter
class NewMarketAdapter(MarketAdapter):
    market_id = "new_market"
    market_name = "新市场"
    description = "新市场描述"

    def get_data_config(self) -> DataConfig:
        return DataConfig(provider_uri=..., data_dir=..., market=...)

    def get_qlib_provider_uri(self) -> str:
        return "/path/to/qlib/data"

    def get_backtest_config(self) -> BacktestConfig:
        return BacktestConfig(annualization_days=252, ...)

    def get_factor_set(self) -> dict[str, str]:
        return {"FACTOR1": "expression1", ...}

    def get_prop_setting_class(self) -> str:
        return "rdagent.app.qlib_rd_loop.conf.FactorBasePropSetting"

    def get_env_overrides(self) -> dict[str, str]:
        return {"KEY": "value", ...}
```

2. 在 `market_adapters/__init__.py` 添加 import:
```python
from . import a_share, crypto, hong_kong, us_stock, new_market  # noqa
```

3. 前端市场按钮会自动从 `GET /api/v1/alpha-agent/markets` 加载。

## 市场配置

### A股 (a_share)
- 数据: Qlib cn_data (CSI300)
- 因子集: Alpha158 子集 (24 因子)
- 年化: 252 天
- 涨跌停: 10%
- 最低佣金: 5 元
- 复权: 需要

### 加密货币 (crypto)
- 数据: Binance 公开 API (35 交易对)
- 因子集: CryptoAlpha (74 因子，专为 7×24 市场设计)
- 年化: 365 天
- 涨跌停: 无
- 佣金: 按比例
- 复权: 不需要
- 环境变量: `CRYPTO_MODE=true`

### 港股 (hong_kong) — 预留
- 数据: 待接入
- 因子集: 暂用 A 股因子集

### 美股 (us_stock) — 预留
- 数据: 待接入
- 因子集: 暂用 A 股因子集

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/alpha-agent/markets` | 列出所有可用市场及数据就绪状态 |
| POST | `/api/v1/alpha-agent/evolve` | 启动因子挖掘 (参数: `market`, `direction`, `loop_n`) |
| GET | `/api/v1/alpha-agent/tasks` | 列出任务 (可按 `market` 过滤) |
| GET | `/api/v1/alpha-agent/factors` | 列出因子 (可按 `market` 过滤) |
| GET | `/api/v1/alpha-agent/stats` | 因子统计 (可按 `market` 过滤) |

## 加密货币数据管线

```python
from backend.services.engine.rd_agent.data_pipeline.crypto_data import (
    download_all_crypto,
    convert_h5_to_qlib_format,
)

# 下载 Binance K线数据 → H5
h5_path = download_all_crypto(start_date="2024-01-01")

# H5 → Qlib bin 格式
convert_h5_to_qlib_format(h5_path)
```

默认交易对 (35 个): BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, ...

## 依赖

- `rd-agent/` — Microsoft RD-Agent (pip install 到 Docker 镜像中)
- `rdagent.app.qlib_rd_loop.factor.FactorRDLoop` — 因子挖掘循环
- `rdagent.app.qlib_rd_loop.conf.FactorBasePropSetting` — 因子配置

## 与 AlphaAgent 的关系

- **AlphaAgent** (`alphaagent/`): 精简版 fork，仅支持 A 股，自定义循环 (`AlphaAgentLoop`)
- **RD-Agent** (`rdagent/`): 完整版 Microsoft RD-Agent，支持多场景 (qlib/kaggle/finetune/...)
- 本框架以 RD-Agent 为核心，通过 MarketAdapter 模式统一管理多市场配置
- 旧的 AlphaAgent 入口 (`scripts/alpha_agent/run.py`) 保留作为备用
