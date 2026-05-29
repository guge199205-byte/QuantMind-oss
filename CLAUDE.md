# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ 免责声明

本项目仅供学习研究与技术演示，不构成任何投资建议。本系统产出的所有分析报告和交易信号均由 AI 自动生成，可能存在错误或偏差。投资决策请咨询持有中国证监会颁发资质的专业机构。作者不对使用本工具产生的任何投资损失承担责任。股市有风险，投资需谨慎。

## Project Overview

QuantMind is a quantitative trading platform with Python backend (FastAPI) and Electron/React/TypeScript frontend. The OSS edition uses single-container deployment where all backend services run in one container.

## Backend Services (all via `backend/main_oss.py`)

| Service | Port | Responsibility |
|---------|------|----------------|
| api | 8000 | User auth, strategy management, community, news proxy |
| engine | 8001 | Qlib backtesting, AI strategy generation, model inference, Alpha Agent |
| trade | 8002 | Order management, positions, risk control |
| stream | 8003 | Real-time quotes, WebSocket push |

## Commands

### Backend
```bash
# Start all services (Docker)
docker-compose up -d

# Run single service locally
SERVICE_MODE=api python backend/main_oss.py

# Tests (run from project root)
python backend/run_tests.py unit        # Unit tests
python backend/run_tests.py integration # Integration tests
python backend/run_tests.py all         # All tests
python backend/run_tests.py trade-long-short  # QMT MVP chain tests

# Lint/format
ruff check backend/
ruff format backend/
```

### Frontend (Electron app in `electron/`)
```bash
npm install              # Install dependencies
npm run dev              # Development (Electron desktop)
npm run dev:web          # Development (Web browser)
npm run typecheck        # Type check
npm run dashboard:build  # Production build
```

## Architecture Notes

- **Feature engineering**: 48-dim features written to `market_data_daily` table by external service
- **Trade service**: Enforces "local-first" order persistence before external submission
- **Redis DB allocation**: 0=general, 1=auth, 2=trade, 3=market, 4=backtest, 5=cache
- **Shared modules**: `backend/shared/` contains cross-service code (DB manager, Redis client, config, logging)
- **Strategy storage**: `backend/shared/strategy_storage.py` is the single entry point for all strategy CRUD operations
- **Alpha Agent**: `backend/services/engine/alpha_agent/` - Factor evolution launcher, supports multi-market via RD-Agent
- **RD-Agent Integration**: `backend/services/engine/rd_agent/` - Multi-market factor mining framework wrapping Microsoft RD-Agent
  - `market_adapters/` - MarketAdapter pattern: a_share, crypto, hong_kong, us_stock
  - `rd_loop_wrapper.py` - Wraps RD-Agent's FactorRDLoop for QuantMind
  - `data_pipeline/` - Market-specific data download and format conversion
- **Data Platform**: `backend/services/engine/data_platform/` - Multi-market data aggregation (A/HK/US), adapters for different data sources
- **TradingAgents**: `backend/services/engine/trading_agents/` - Multi-agent A-share research framework (7 AI analysts, debate, risk assessment)
  - `runner.py` - Background thread runner for TradingAgentsGraph pipeline
  - `progress.py` - Thread-safe progress tracker (12 stages)
  - `routers/trading_agents.py` - REST API (analyze, progress, report, history, download)
- **Data Pipeline**: `backend/scripts/` - Unified daily data sync
  - `daily_data_sync.py` - Main sync: investment_data → baostock → akshare → eltdx → PG → Qlib bin → indicators → parquet
  - `sync_investment_data.py` - GitHub releases qlib_bin download and extraction
  - `update_feature_parquet.py` - 151-dim feature computation (momentum/volatility/liquidity/fund flow/style)
- **News/RSS**: Huntly + RSSHub for financial news aggregation, proxied through API service

## Stock Code Standardization

- **Internal Format**: Prefix-based (e.g., `SH600036`) for database storage
- **API Format**: Suffix-based (e.g., `600036.SH`) for kline API and Qlib
- **Normalization Utilities**:
  - **Backend**: `backend/shared/stock_utils.py` -> `StockCodeUtil.to_prefix(code)`
  - **Frontend**: `electron/src/utils/portfolioUtils.ts` -> `normalizeStockCode(code)`
  - **Dashboard**: `electron/src/features/dashboard/pages/DashboardPage.tsx` -> `normalizeSymbol(raw)` converts `SZ300258` → `300258.SZ`
- **Market Auto-Identification**:
  - `SH`: 6xxxxx, 9xxxxx
  - `SZ`: 0xxxxx, 3xxxxx, 2xxxxx
  - `BJ`: 4xxxxx, 8xxxxx
  - `HK`: 5-digit codes or `.HK` suffix
  - `US`: Ticker symbols without numeric prefix

## Environment

Required `.env` keys (defaults in `docker-compose.yml`):
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `REDIS_HOST`, `REDIS_PORT`
- `SECRET_KEY`, `JWT_SECRET_KEY`
- `STORAGE_MODE=local` for OSS edition

## Code Style

- Python: Line length 88, use ruff for linting/formatting
- TypeScript: Run `npm run typecheck` before committing frontend changes

## Deployment Workflow

After making code changes, always:
1. **Commit to git**: Create a commit with descriptive message
2. **Deploy to server**: SSH to `quant-server` and pull/deploy updates

```bash
# Local: commit changes
git add .
git commit -m "descriptive message"

# Deploy to quant-server
ssh quant-server "cd /opt/quantmind && git pull && docker-compose restart"

# Deploy frontend (if changed)
cd electron && npm run build
docker cp dist-react/. quantmind-web:/usr/share/nginx/html/
```

## Key Files

- `backend/main_oss.py` - Unified entry point for all backend services
- `backend/run_tests.py` - Test runner with multiple modes
- `backend/shared/` - Shared modules across services
- `backend/services/engine/alpha_agent/launcher.py` - Factor evolution launcher (supports market parameter)
- `backend/services/engine/rd_agent/market_adapters/` - Market adapter registry (a_share, crypto, hong_kong, us_stock)
- `backend/services/engine/rd_agent/rd_loop_wrapper.py` - RDLoop wrapper bridging RD-Agent and QuantMind
- `backend/services/engine/routers/alpha_agent.py` - Alpha Agent API (includes /markets, /evolve with market param)
- `backend/services/engine/routers/trading_agents.py` - TradingAgents REST API (analyze, progress, report, history)
- `backend/services/engine/trading_agents/runner.py` - TradingAgents background thread runner
- `backend/services/engine/trading_agents/progress.py` - TradingAgents progress tracker (12 stages)
- `scripts/alpha_agent/run_rd_agent.py` - RD-Agent multi-market runner script (subprocess entry point)
- `backend/services/engine/data_platform/` - Multi-market data platform
- `backend/scripts/daily_data_sync.py` - Unified daily data sync (PG + Qlib + indicators + parquet)
- `backend/scripts/sync_investment_data.py` - GitHub investment_data download and extraction
- `backend/scripts/update_feature_parquet.py` - 151-dim feature parquet computation
- `backend/services/api/routers/admin/data_platform.py` - Admin data platform endpoints (sync, parquet, health)
- `backend/services/api/routers/news.py` - News proxy router
- `backend/services/api/routers/market_kline.py` - K-line market data router
- `electron/src/features/trading-agents/` - TradingAgents frontend module (pages, components, services)
- `docker-compose.yml` - Local deployment configuration
