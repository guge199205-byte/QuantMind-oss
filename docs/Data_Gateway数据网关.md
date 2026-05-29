# Data Gateway 数据网关服务

多数据源金融数据统一网关，聚合 akshare / 东方财富 数据，为 QuantMind 各模块提供行情、历史 K 线、技术指标等标准化接口。

## 服务信息

| 项目 | 值 |
|------|-----|
| 端口 | 8004 |
| 入口 | `backend/services/engine/data_gateway/main.py` |
| Docker | `docker/Dockerfile.data-gateway` |
| 代理路径 | `/api/v1/data/*` → `data-gateway:8004/api/v1/*` |

## 目录结构

```
backend/services/engine/data_gateway/
├── main.py                          # FastAPI 入口
├── config.py                        # 服务配置
├── providers/
│   ├── akshare_provider.py          # AKShare 数据源
│   └── eastmoney_provider.py        # 东方财富数据源
└── routers/
    ├── market.py                    # 行情路由
    └── technical.py                 # 技术指标路由
```

## API 接口

### 行情 `/api/v1/market`

| 接口 | 方法 | 说明 | 默认数据源 |
|------|------|------|-----------|
| `/quote` | GET | 实时行情 | auto (eastmoney→akshare) |
| `/historical` | GET | 历史 K 线 | auto (akshare→eastmoney) |
| `/search` | GET | 搜索股票 | auto (eastmoney→akshare) |
| `/overview` | GET | 市场概览 | akshare |
| `/indices` | GET | 主要指数 | akshare |
| `/sectors` | GET | 热门板块 | akshare |
| `/fund-flow` | GET | 资金流向 | eastmoney |

**常用参数：**
- `symbol`: 股票代码（纯数字，如 `600519`）
- `provider`: 数据源选择（`auto` / `akshare` / `eastmoney`）
- `days`: 历史天数（默认 365）
- `period`: 周期（`daily` / `weekly` / `monthly`）
- `adjust`: 复权（`qfq` 前复权 / `hfq` 后复权 / `none`）

### 技术指标 `/api/v1/technical`

| 接口 | 说明 |
|------|------|
| `/ma` | 移动平均线 (MA5/10/20/60) |
| `/macd` | MACD (line/signal/histogram) |
| `/rsi` | RSI(14) |
| `/kdj` | KDJ (K/D/J) |
| `/boll` | 布林带 (upper/middle/lower) |
| `/all` | 全部指标（18 项） |

返回格式：`{success, data: {指标名: [数值...]}, dates: [日期...]}`

## 数据源策略

### 自动降级机制

每个接口默认 `provider=auto`，按优先级尝试：

1. **主数据源**调用 → 成功则返回
2. **主数据源失败** → 自动切换备用数据源
3. **两源均失败** → 返回 500 错误

| 场景 | 主数据源 | 备用数据源 |
|------|---------|-----------|
| 实时行情 | eastmoney (轻量 HTTP) | akshare (历史数据兜底) |
| 历史 K 线 | akshare (stock_zh_a_hist) | akshare (stock_zh_a_daily) → eastmoney |
| 搜索 | eastmoney | akshare |

### AkShare 数据源

- `stock_zh_a_hist()`: 主力历史数据，支持日期范围和复权
- `stock_zh_a_daily()`: 备用历史数据（Docker 内稳定可用，无日期过滤）
- `stock_zh_a_spot_em()`: 全市场快照（Docker 内易超时，仅做主尝试）
- `stock_info_a_code_name()`: 股票搜索

### 东方财富数据源

- `push2.eastmoney.com/api/qt/stock/get`: 实时行情（轻量，Docker 内稳定）
- `push2.eastmoney.com/api/qt/stock/kline/get`: 历史 K 线（Docker 内偶发连接重置）
- `searchapi.eastmoney.com/api/suggest/get`: 搜索
- `push2.eastmoney.com/api/qt/stock/fflow/get`: 资金流向

**注意事项：**
- 东方财富 kline 接口在 Docker 环境中偶发 `RemoteDisconnected`，已加 httpx 指数退避重试
- AkShare `stock_zh_a_spot_em()` 拉取全市场数据，Docker 内易超时，仅在 eastmoney 失败时作为兜底

## 技术指标计算

使用 `ta` 库计算，NaN/inf 值自动替换为 `null`（JSON 安全）。

支持指标：MA、EMA、MACD、RSI、KDJ、BOLL、OBV、ATR

## 测试验证

```bash
# 直接访问 data-gateway
curl http://localhost:8004/api/v1/market/quote?symbol=600519
curl http://localhost:8004/api/v1/market/historical?symbol=600519&days=30
curl http://localhost:8004/api/v1/technical/macd?symbol=600519
curl http://localhost:8004/api/v1/technical/all?symbol=600519
curl http://localhost:8004/api/v1/market/search?keyword=茅台

# 通过 API 代理访问
curl http://localhost:8000/api/v1/data/market/quote?symbol=600519
curl http://localhost:8000/api/v1/data/technical/all?symbol=600519
```

## 后续规划：OpenBB 集成

当前 data-gateway 已实现 akshare + eastmoney 双数据源。后续接入 OpenBB 可按以下路径扩展：

1. **新增 `providers/openbb_provider.py`**：封装 OpenBB Platform API 调用
2. **新增 `routers/openbb.py`**：美股、加密货币、宏观经济数据接口
3. **扩展 auto 降级链**：A 股场景保持 akshare→eastmoney，全球数据走 OpenBB
4. **统一数据格式**：OpenBB DataFrame 列名映射到现有 `trade_date/open/close/high/low/volume` 标准

OpenBB 可提供的增量数据：
- 美股行情与财务数据
- 加密货币行情
- 宏观经济指标（GDP、CPI、利率等）
- 另类数据（新闻情绪、SEC 文件等）
