# Stock Query Service

智能股票筛选与查询服务。

## 功能特性

### 1. 智能选股 (Core AI)
- **自然语言交互**: 支持通过自然语言描述选股条件（如“找出低估值科技股”）。
- **多轮对话**: 支持基于上下文的细化筛选 (`/api/smart-screener/refine`).
- **本地数据驱动**: 完全基于本地数据库 (`Stocks`, `StockRealTimeData`) 进行筛选，无需外部数据源依赖。
- **无需 Tushare**: 已移除 Tushare 依赖，确保数据自主可控。

### 2. 基础查询
- **股票信息**: 提供股票基础信息查询 (`/api/v1/stocks/{symbol}`).
- **实时报价**: 获取股票最新报价 (`/api/v1/stocks/{symbol}/quote`).
- **市场概览**: 获取大盘指数和市场状态 (`/api/v1/market/overview`).

### 3. 数据要求
- 企业级金融业务禁止内置任何演示/模拟数据接口。
- 所有查询必须基于真实数据源与本地数据库数据（由数据同步/ETL 任务持续补齐）。

## 技术架构
- **API Framework**: FastAPI
- **Database**: SQLAlchemy + PostgreSQL
- **AI Engine**: OpenAI API (用于 Query Parsing)
- **Data Source**: Local Database (替代 Tushare)

## 快速开始

### 环境变量
确保配置以下环境变量：
```bash
# OpenAI API Key (用于智能选股解析)
export OPENAI_API_KEY="sk-..."

# 数据库连接 (用于本地数据查询)
export DATABASE_URL="postgresql+psycopg2://user:pass@localhost:5432/quantmind"
```

### 启动服务
```bash
# 激活虚拟环境
source .venv/bin/activate

# 启动服务 (默认端口 8018)
python main.py
```

## API 文档
启动服务后访问: `http://localhost:8018/docs`

### 核心接口
- `POST /api/smart-screener/query`: 智能选股
- `GET /api/smart-screener/suggestions`: 获取选股建议
- `GET /api/v1/stocks/search`: 关键词搜索股票

## 最近更新
- **[2024-05]**: 移除 Tushare 依赖，重构 `DataAggregator` 使用本地数据库。
- **[2024-05]**: 启用 `smart_screener_api`，开放 AI 选股接口。
- **[2024-05]**: 移除 `data_service` 演示数据接口，统一走真实数据链路。
- **[2026-03-20]**: 修复 `/api/v1/stocks/{symbol}` 路由对 `QueryResponse` 的错误访问（将对象误当作 dict 调用 `.get` 导致 500）；现统一返回 `QueryResponse.to_dict()`，并按 `data` 判定 404，避免前端持仓名称回填失败。
- **[2026-03-20]**: 修复 `StockQueryService` 缓存读写异步调用错误（`cache_manager.get/set` 补齐 `await`），消除 `coroutine object is not subscriptable` 异常，恢复股票详情接口稳定性。
- **[2026-03-20]**: 修复本地股票查询的数据库驱动归一：当运行时 `DATABASE_URL` 为 `postgresql+asyncpg://` 时，`local_models` 会自动转换为同步 `postgresql+psycopg2://` 再创建 `create_engine`，避免 `greenlet_spawn has not been called` 异常。
- **[2026-03-20]**: `get_stock_info` 新增本地索引回退：当 `stocks` 表缺失/查询异常时，自动回退读取 `data/stocks/stocks_index.json` 返回 `code/name`，保障持仓页面股票名称可回填。
