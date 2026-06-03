<h1 align="center">QuantMind</h1>

<p align="center">
  <strong>AI 驱动的多市场量化交易平台</strong>
</p>

<p align="center">
  数据采集 → 因子挖掘 → 模型训练 → 策略回测 → 智能推理 → 实盘交易
</p>

<p align="center">
  <a href="#-快速开始">快速开始</a> •
  <a href="#-系统架构">系统架构</a> •
  <a href="#-多市场数据">多市场数据</a> •
  <a href="#-ai-能力">AI 能力</a> •
  <a href="#-部署指南">部署指南</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Node.js-20+-green.svg" alt="Node.js">
  <img src="https://img.shields.io/badge/License-AGPL%20v3-blue.svg" alt="License">
  <img src="https://img.shields.io/badge/Qlib-Powered-orange.svg" alt="Qlib">
</p>

---

## 项目简介

QuantMind 是一个端到端的量化交易平台，集成了微软 Qlib 量化框架和 RD-Agent 智能体，支持 A 股、港股、美股、加密货币四个市场。

**核心能力：**
- **多市场数据管线** — 自动采集、清洗、校准 A/HK/US/Crypto 行情数据
- **AI 因子挖掘** — 基于 RD-Agent 的自动化因子进化
- **模型训练与推理** — Alpha158 + LightGBM，支持增量训练和自动推理
- **策略生成** — AI 辅助生成 Qlib 策略代码，支持自然语言交互
- **回测引擎** — 基于 Qlib 的高性能回测，支持多策略对比
- **投研平台** — 多 Agent 协作的 A 股研究报告生成

---

## 快速开始

### 环境要求

- Docker & Docker Compose
- 8GB+ 内存（推荐 16GB）
- 50GB+ 磁盘空间（含数据）

### 一键部署

```bash
# 克隆仓库
git clone https://github.com/guge199205-byte/QuantMind-oss.git
cd QuantMind-oss

# 配置环境变量
cp .env.example .env
# 编辑 .env，设置 DB_PASSWORD、SECRET_KEY 等

# 启动所有服务
docker compose up -d

# 查看日志
docker compose logs -f api
```

服务启动后：
- **Web 界面**: http://localhost:3000
- **API 文档**: http://localhost:8000/docs
- **引擎服务**: http://localhost:8001

### 下载市场数据

从 [Releases](https://github.com/guge199205-byte/QuantMind-oss/releases) 下载数据文件：

```bash
# 下载港股数据（41MB H5 + 24MB Qlib）
wget https://github.com/guge199205-byte/QuantMind-oss/releases/download/v1.0.0-data/hk_data_h5.tar.gz
wget https://github.com/guge199205-byte/QuantMind-oss/releases/download/v1.0.0-data/hk_qlib_data.tar.gz

# 解压到 db 目录
tar xzf hk_data_h5.tar.gz -C db/
tar xzf hk_qlib_data.tar.gz -C db/

# 复制到 Docker 容器
docker cp db/hk_data quantmind:/app/db/
docker cp db/qlib_data/hk_data quantmind:/app/db/qlib_data/

# 美股、加密货币同理
```

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Electron 桌面端                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ 仪表盘   │ │ 策略向导 │ │ 回测中心 │ │ 投研平台 │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP/WebSocket
┌───────────────────────────┴─────────────────────────────────────┐
│                      API Gateway (Nginx)                        │
└───┬──────────┬──────────┬──────────┬────────────────────────────┘
    │          │          │          │
    ▼          ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│ API   │ │Engine │ │Trade  │ │Stream │
│ :8000 │ │ :8001 │ │ :8002 │ │ :8003 │
└───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘
    │         │         │         │
    ▼         ▼         ▼         ▼
┌───────────────────────────────────────┐
│          PostgreSQL + Redis           │
└───────────────────────────────────────┘
```

### 服务职责

| 服务 | 端口 | 职责 |
|------|------|------|
| **api** | 8000 | 用户认证、策略管理、社区、新闻代理 |
| **engine** | 8001 | Qlib 回测、AI 策略生成、模型推理、Alpha Agent |
| **trade** | 8002 | 订单管理、持仓、风控 |
| **stream** | 8003 | 实时行情、WebSocket 推送 |

### 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Electron + React + TypeScript + Ant Design |
| **后端** | Python + FastAPI + SQLAlchemy + Celery |
| **量化** | Qlib + LightGBM + RD-Agent |
| **数据库** | PostgreSQL + Redis |
| **部署** | Docker Compose + Nginx |

---

## 多市场数据

QuantMind 支持四个市场的数据采集和管理：

### 数据表结构

| 市场 | 表名 | 数据源 | 覆盖范围 |
|------|------|--------|----------|
| A 股 | `stock_daily_latest` | investment_data + baostock | 2010 ~ 今 |
| 港股 | `stock_daily_latest_hk` | Parquet + yfinance | 2020 ~ 今 |
| 美股 | `stock_daily_latest_us` | yfinance | 2020 ~ 今 |
| 加密货币 | `stock_daily_latest_crypto` | Binance API | 2020 ~ 今 |

### 数据管线

```
原始数据源 → PostgreSQL → 技术指标计算 → Qlib bin → H5 文件 → 特征工程 Parquet
```

每个市场包含 35+ 技术指标：
- **均线**: MA5/10/20/60, 距均线偏离度
- **动量**: RSI(6/14), MACD(12/26/9), KDJ(9)
- **波动**: ATR(14/20), 标准差, 下行波动率
- **资金**: VPIN, 量比, 换手率
- **风格**: Beta, 特质波动率, 市值因子

### A 股数据同步

A 股数据通过 `daily_data_sync.py` 自动同步：

```bash
# 手动触发同步
python backend/scripts/daily_data_sync.py

# 仅同步行情数据
python backend/scripts/daily_data_sync.py --skip-indicators

# 仅计算指标
python backend/scripts/daily_data_sync.py --indicators-only
```

同步流程：
1. 拉取 investment_data（GitHub releases）
2. 更新 baostock 日线
3. 合并数据到 PostgreSQL
4. 生成 Qlib bin 格式
5. 计算 35+ 技术指标
6. 生成特征 Parquet（151 维）

### 港股数据导入

```bash
# 从 Parquet 文件导入（2020-2026）
python backend/scripts/import_hk_parquet.py --since 2020

# 从 yfinance 同步近期数据
python backend/scripts/sync_hk_recent.py --since 2026-05-09

# 重建 H5 和 Qlib 格式
python backend/scripts/rebuild_hk_h5.py --qlib
```

### 数据管理

管理员可通过 Web 界面管理数据：
- **数据管理** → 查看各市场数据状态
- **同步数据** → 触发增量同步
- **更新特征** → 重新计算特征 Parquet
- **同步基本面** → 更新 PE/PB/ROE 等指标

---

## AI 能力

### 1. AI 策略生成（AI-IDE）

自然语言描述策略需求，AI 自动生成 Qlib 策略代码：

```
用户: 帮我写一个港股动量策略，选 RSI 低于 30 的股票，MA5 金叉 MA20 时买入
AI: [生成完整的 Qlib 策略代码，包含选股、买入、卖出、风控逻辑]
```

支持的市场：
- **CN** — A 股，使用 `/app/db/qlib_data` 数据
- **HK** — 港股，使用 `/app/db/qlib_data/hk_data` 数据
- **US** — 美股，使用 `/app/db/qlib_data/us_data` 数据
- **CRYPTO** — 加密货币，使用 `/app/db/qlib_data/crypto_data` 数据

### 2. RD-Agent 因子挖掘

基于微软 RD-Agent 的自动化因子进化：

```bash
# 启动因子进化
POST /api/v1/alpha-agent/evolve
{
  "market": "hong_kong",
  "iterations": 10
}
```

流程：
1. 从市场数据中提取候选因子
2. 使用 LLM 生成因子假设
3. 回测验证因子有效性
4. 迭代优化，保留有效因子

### 3. TradingAgents 投研

多 Agent 协作的 A 股研究框架（7 个 AI 分析师）：

- **基本面分析师** — 财报、估值分析
- **技术分析师** — K 线形态、技术指标
- **消息面分析师** — 新闻、公告解读
- **情绪分析师** — 市场情绪、资金流向
- **风险评估师** — 风险量化、回撤控制
- **辩论模块** — 多空观点碰撞
- **决策模块** — 综合研判，生成报告

### 4. QuantBot 智能助手

自然语言交互，支持：
- 策略查询和修改
- 回测执行和结果解读
- 市场行情问答
- 操作指引

---

## 回测引擎

基于微软 Qlib 的高性能回测：

### 快速回测

```python
from qlib.contrib.strategy import TopkDropoutStrategy
from qlib.backtest import backtest

# 配置策略
strategy = TopkDropoutStrategy(
    signal=pred_signal,
    topk=50,
    n_drop=5,
)

# 执行回测
report, indicator = backtest(
    strategy=strategy,
    start_time="2024-01-01",
    end_time="2024-12-31",
    account=1000000,
)
```

### 回测参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `topk` | 持仓股票数 | 50 |
| `n_drop` | 每次换仓数 | 5 |
| `rebalance_period` | 调仓周期 | 5 天 |
| `benchmark` | 基准指数 | CSI300 |

---

## 项目结构

```
QuantMind-oss/
├── backend/
│   ├── main_oss.py                 # 统一入口
│   ├── shared/                     # 跨服务共享模块
│   │   ├── db_manager.py           # 数据库连接池
│   │   ├── redis_client.py         # Redis 客户端
│   │   ├── stock_utils.py          # 股票代码工具
│   │   └── trading_calendar.py     # 交易日历
│   ├── services/
│   │   ├── api/                    # API 服务
│   │   │   ├── routers/            # 路由定义
│   │   │   └── user_app/           # 用户认证
│   │   ├── engine/                 # 引擎服务
│   │   │   ├── ai_strategy/        # AI 策略生成
│   │   │   ├── qlib_app/           # Qlib 回测
│   │   │   ├── alpha_agent/        # Alpha Agent
│   │   │   ├── rd_agent/           # RD-Agent 因子挖掘
│   │   │   ├── trading_agents/     # TradingAgents 投研
│   │   │   └── routers/            # 引擎路由
│   │   ├── trade/                  # 交易服务
│   │   └── stream/                 # 行情服务
│   └── scripts/
│       ├── daily_data_sync.py      # 每日数据同步
│       ├── import_hk_parquet.py    # 港股 Parquet 导入
│       ├── sync_hk_recent.py       # 港股近期数据同步
│       └── rebuild_hk_h5.py        # H5/Qlib 重建
├── electron/
│   ├── src/
│   │   ├── components/             # UI 组件
│   │   ├── features/               # 功能模块
│   │   │   ├── dashboard/          # 仪表盘
│   │   │   ├── strategy-wizard/    # 策略向导
│   │   │   ├── backtest/           # 回测中心
│   │   │   ├── trading-agents/     # 投研平台
│   │   │   └── admin/              # 管理后台
│   │   ├── services/               # API 调用
│   │   └── config/                 # 配置
│   └── package.json
├── docker/
│   ├── Dockerfile                  # 后端镜像
│   └── nginx.conf                  # Nginx 配置
├── db/                             # 数据目录（gitignore）
│   ├── qlib_data/                  # Qlib bin 格式
│   │   ├── cn_data/                # A 股
│   │   ├── hk_data/                # 港股
│   │   ├── us_data/                # 美股
│   │   └── crypto_data/            # 加密货币
│   ├── hk_data/                    # 港股 H5
│   ├── us_data/                    # 美股 H5
│   └── crypto_data/                # 加密货币 H5
└── docker-compose.yml
```

---

## 部署指南

### 生产环境部署

```bash
# 1. 克隆代码
git clone https://github.com/guge199205-byte/QuantMind-oss.git
cd QuantMind-oss

# 2. 配置环境变量
cat > .env << EOF
DB_HOST=db
DB_PORT=5432
DB_NAME=quantmind
DB_USER=quantmind
DB_PASSWORD=your_secure_password
REDIS_HOST=redis
REDIS_PORT=6379
SECRET_KEY=your_secret_key
JWT_SECRET_KEY=your_jwt_secret
EOF

# 3. 启动服务
docker compose up -d

# 4. 下载数据
# 从 Releases 下载数据文件并解压到 db/

# 5. 初始化数据库
docker exec quantmind python -c "from backend.shared.db_manager import DatabaseManager; DatabaseManager().init_tables()"

# 6. 构建股票索引
docker exec quantmind python backend/services/api/scripts/build_stock_index.py
```

### 前端开发

```bash
cd electron
npm install
npm run dev          # Electron 桌面端
npm run dev:web      # Web 浏览器
npm run typecheck    # 类型检查
```

### 后端开发

```bash
# 单服务启动
SERVICE_MODE=api python backend/main_oss.py
SERVICE_MODE=engine python backend/main_oss.py

# 运行测试
python backend/run_tests.py unit
python backend/run_tests.py integration
```

---

## 定时任务

| 任务 | 时间 | 说明 |
|------|------|------|
| `daily_data_sync` | 18:00 工作日 | A 股数据同步 |
| `auto_inference` | 00:00 工作日 | 模型自动推理 |
| `news_enrich` | 每 1 分钟 | 新闻 AI 增强 |
| `news_reload` | 每 10 分钟 | 新闻规则重载 |

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DB_HOST` | PostgreSQL 主机 | `db` |
| `DB_PORT` | PostgreSQL 端口 | `5432` |
| `DB_NAME` | 数据库名 | `quantmind` |
| `DB_USER` | 数据库用户 | `quantmind` |
| `DB_PASSWORD` | 数据库密码 | - |
| `REDIS_HOST` | Redis 主机 | `redis` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `SECRET_KEY` | 应用密钥 | - |
| `JWT_SECRET_KEY` | JWT 密钥 | - |
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `CHAT_MODEL` | AI 模型 | `gpt-4` |

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！

```bash
# 1. Fork 仓库
# 2. 创建特性分支
git checkout -b feature/your-feature

# 3. 提交更改
git commit -m "feat: add your feature"

# 4. 推送并创建 PR
git push origin feature/your-feature
```

---

## License

[GNU Affero General Public License v3.0](LICENSE)

---

## 免责声明

> **本项目仅供学习研究与技术演示，不构成任何投资建议。**
>
> - 本系统产出的所有分析报告和交易信号均由 AI 自动生成，可能存在错误或偏差
> - 投资决策请咨询持有中国证监会颁发资质的专业机构
> - 作者不对使用本工具产生的任何投资损失承担责任
> - **股市有风险，投资需谨慎**

---

## 致谢

- [Qlib](https://github.com/microsoft/qlib) — 微软量化投资平台
- [RD-Agent](https://github.com/microsoft/RD-Agent) — 微软研发智能体
- [TradingAgents-Astock](https://github.com/simonlin1212/TradingAgents-astock) — 多 Agent A 股投研
- [FastAPI](https://fastapi.tiangolo.com/) — 高性能 Web 框架
- [investment_data](https://github.com/chenditc/investment_data) — A 股历史行情数据

---

<p align="center">
  <strong>QuantMind</strong> — AI 驱动的量化交易
</p>
