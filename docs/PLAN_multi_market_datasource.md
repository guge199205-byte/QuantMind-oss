# Multi-Market & Multi-Source Data Platform — 完整规划 v2

> 起草日期：2026-05-24
> 更新：v2 — 采纳「字段聚合层」+ 数据清洗/校验 + 全源接入 + 实时/分钟/订单流 + 多市场交易日历
> 设计原则：**字段级聚合** + **多层清洗** + **市场级日历驱动** + **插件式数据源**

---

## 0. 现状盘点（同 v1）

- 已有 `DataSourceAdapter` 抽象基类（仅覆盖实时行情 3 方法）
- 已有 `sync_investment_data.py` 同步 chenditc A 股日线到 Qlib bin
- 已有 `stock_daily_latest` PostgreSQL 表（A 股核心字段）
- 已有 `db/qlib_data/` 本地 Qlib bin（只有 A 股）
- 缺：离线统一适配层、多市场、字段聚合、健康监控、清洗 / 校验、交易日历服务

---

## 1. 总体架构（v2 核心）

```
                   ┌────────────────────────────────────────────────┐
                   │             前端 / API Gateway                  │
                   └────────────────┬───────────────────────────────┘
                                    │
              ┌─────────────────────▼──────────────────────┐
              │       字段聚合服务 FieldAggregator           │
              │  「我要 000001 的财报」→ 查路由表 → 拿主源 │
              │   失败 → fallback 备用源 → 多源一致性投票  │
              └─────────────────────┬──────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
┌───────▼───────┐         ┌─────────▼─────────┐         ┌───────▼────────┐
│ 清洗 / 校验层  │         │  交易日历服务      │         │  健康监控层     │
│ DataCleaner   │         │ TradingCalendar    │         │ HealthMonitor  │
│ - 范围校验     │         │ - A/HK/US 三套     │         │ - 源 × 字段     │
│ - 异常检测     │         │ - 节假日/半日      │         │ - 延迟/错误率   │
│ - 多源投票     │         │ - 开闭盘时间       │         │ - 一致性偏差    │
│ - 复权对齐     │         │ - cron 触发判定    │         │ - Slack/邮件    │
└───────┬───────┘         └─────────┬─────────┘         └───────┬────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
        ┌───────────────────────────▼───────────────────────────┐
        │                  插件适配器层 Adapters                  │
        │  investment_data │ baostock │ efinance │ qstock │ ...  │
        │  eltdx │ tdx-api │ akshare │ yfinance │ sec_xbrl │ ... │
        └───────────────────────────┬───────────────────────────┘
                                    │
        ┌───────────────────────────▼───────────────────────────┐
        │            存储层 (Parquet 中间层 + Qlib bin + PG)     │
        └───────────────────────────────────────────────────────┘
```

---

## 2. 字段聚合层 FieldAggregator（核心）

### 2.1 字段路由表（YAML 配置，运维可热更新）

`config/data_sources/field_routing.yaml`：
```yaml
markets:
  A:
    # 日线 OHLCV
    daily_kline:
      primary: investment_data
      fallback: [baostock, efinance, mootdx]
      consensus: median        # 多源投票时取中位数
      tolerance_pct: 0.5       # close 偏差超 0.5% 标记异常

    # 实时盘口（5档）
    realtime_quote:
      primary: eltdx
      fallback: [tdx_api, tencent, sina]
      stream: true             # 走 WebSocket 流式
      ttl_sec: 3

    # 分钟K线 (1m/5m/15m/30m/60m)
    minute_kline:
      primary: eltdx
      fallback: [mootdx, tdx_api]
      consensus: none          # 实时数据不投票

    # 逐笔成交
    tick:
      primary: eltdx
      fallback: [tdx_api]
      stream: true

    # 集合竞价
    auction:
      primary: eltdx
      fallback: [tdx_api]

    # 财报（季报 37 字段 + 三表）
    financial_report:
      primary: simonlin_a_stock
      fallback: [efinance, baostock, mootdx]
      cache_hours: 24

    # F10 九大类
    f10:
      primary: simonlin_a_stock
      fallback: [efinance]
      cache_hours: 168         # 一周

    # 龙虎榜 / 全市场龙虎榜
    dragon_tiger:
      primary: simonlin_a_stock
      fallback: [efinance]

    # 资金流（主力/大单/中单/小单 + 北向）
    money_flow:
      primary: simonlin_a_stock
      fallback: [efinance, qstock]

    # 融资融券
    margin_trading:
      primary: simonlin_a_stock
      fallback: [efinance]

    # 大宗交易
    block_trade:
      primary: simonlin_a_stock
      fallback: [efinance]

    # 股东户数
    shareholder_count:
      primary: simonlin_a_stock
      fallback: [efinance]

    # 分红送转 / 解禁
    dividend:
      primary: simonlin_a_stock
      fallback: [efinance, baostock]
    share_unlock:
      primary: simonlin_a_stock
      fallback: [efinance]

    # 研报（列表/PDF/一致预期/NL搜索）
    research_report:
      primary: simonlin_a_stock
      fallback: []

    # 选股（RPS/MM趋势/财务指标/资金流模型）
    stock_screening:
      primary: qstock
      fallback: []

    # 强势股 / 题材归因 / 概念板块
    hot_signal:
      primary: simonlin_a_stock
      fallback: [qstock, efinance]

    # 公告（沪深北全量）
    announcement:
      primary: simonlin_a_stock
      fallback: [mootdx]

    # 新闻 / 财联社快讯
    news:
      primary: simonlin_a_stock
      fallback: []

    # 期货
    futures_kline:
      primary: efinance
      fallback: []

    # 板块
    sector:
      primary: efinance
      fallback: [simonlin_a_stock]

    # 复权因子
    adj_factor:
      primary: investment_data
      fallback: [baostock, eltdx]

    # 股本变化
    share_change:
      primary: eltdx
      fallback: [baostock]

  HK:
    daily_kline:
      primary: yfinance
      fallback: [akshare, simonlin_global]
      tolerance_pct: 0.5

    realtime_quote:
      primary: simonlin_global    # gb_/rt_hk 25-78 字段最丰富
      fallback: [tencent_r_hk]
      stream: true
      ttl_sec: 3

    minute_kline:
      primary: simonlin_global    # yahoo chart
      fallback: [yfinance]

    financial_report:
      primary: simonlin_global    # 东财 + yahoo
      fallback: [yfinance]

    f10:
      primary: simonlin_global
      fallback: []

    technical_indicators:         # MA/EMA/MACD/RSI/KDJ/布林
      primary: simonlin_global    # 库内已算好
      fallback: []                # 也可本地用 QuantBot 重算

  US:
    daily_kline:
      primary: simonlin_global    # 新浪回溯到 1984
      fallback: [yfinance]

    realtime_quote:
      primary: simonlin_global    # 东财 push2
      fallback: [yfinance]
      stream: true
      ttl_sec: 3

    minute_kline:
      primary: yfinance
      fallback: [simonlin_global]

    financial_report:
      primary: simonlin_global    # 东财三表 + GMAININDICATOR + Yahoo
      fallback: [yfinance]
      cache_hours: 24

    sec_filing:                   # 10-K/10-Q/8-K + 503 GAAP
      primary: simonlin_global    # EDGAR submissions + XBRL
      fallback: []
      cache_hours: 168

    options_chain:                # 期权链
      primary: simonlin_global    # Yahoo crumb
      fallback: []

    money_flow:
      primary: simonlin_global    # push2his
      fallback: []

    institutional_holdings:       # 机构持仓
      primary: simonlin_global
      fallback: [yfinance]
```

### 2.2 聚合器逻辑

```python
class FieldAggregator:
    async def get(self, market: str, field: str, symbol: str, **kw):
        route = self.routing[market][field]
        primary = self.adapters[route['primary']]

        # 1. 主源
        try:
            data = await primary.fetch(field, symbol, **kw)
            data = self.cleaner.clean(market, field, data, source=route['primary'])
            self.monitor.record_success(route['primary'], field)
            return data
        except Exception as e:
            self.monitor.record_error(route['primary'], field, e)

        # 2. fallback
        for src in route.get('fallback', []):
            try:
                data = await self.adapters[src].fetch(field, symbol, **kw)
                data = self.cleaner.clean(market, field, data, source=src)
                self.monitor.record_fallback(route['primary'], src)
                return data
            except Exception:
                continue

        # 3. 全失败
        raise DataUnavailable(market, field, symbol)

    async def get_consensus(self, market, field, symbol, **kw):
        """多源投票模式：拿 N 个源同时取，取中位数 / 一致值"""
        route = self.routing[market][field]
        sources = [route['primary']] + route.get('fallback', [])
        results = await asyncio.gather(*[
            self.adapters[s].fetch(field, symbol, **kw) for s in sources
        ], return_exceptions=True)
        valid = [r for r in results if not isinstance(r, Exception)]
        if not valid:
            raise DataUnavailable(market, field, symbol)
        return self.cleaner.consensus(valid, method=route.get('consensus', 'median'))
```

---

## 3. 清洗 / 校验层 DataCleaner（新增）

### 3.1 4 层清洗

| 层 | 职责 | 例子 |
|---|---|---|
| L1 Schema 校验 | 字段存在、类型、NOT NULL | symbol/trade_date 必填，price > 0 |
| L2 范围校验 | 业务合理性 | 涨跌幅 ≤ ±20%（创业板 ±30%、ST ±5%），volume ≥ 0，PE ∈ [-1000, 10000] |
| L3 异常检测 | 时序异常 | 当日 close 比昨日 ×3 → 标记 outlier_flag=true，不写入主表 |
| L4 多源一致性 | 跨源投票 | 3 个源中 2 个 close=10.5，1 个 close=105 → 取 10.5 + 报警 |

```python
class DataCleaner:
    def clean(self, market: str, field: str, df: pd.DataFrame, source: str) -> pd.DataFrame:
        df = self._validate_schema(field, df)              # L1
        df = self._validate_range(market, field, df)       # L2
        df, anomalies = self._detect_outliers(field, df)   # L3
        self._persist_anomalies(market, field, source, anomalies)
        return df

    def consensus(self, dfs: list[pd.DataFrame], method='median') -> pd.DataFrame:
        # 按 (symbol, trade_date) 对齐 → 数值字段取 median，字符串字段取众数
        # 偏差超过阈值的写入 data_quality_alerts
        ...
```

### 3.2 准确率保证机制

1. **每日校验任务**（Celery cron）
   - 每个收盘后跑：抽样 10% 标的，对比 ≥2 个源的 close/volume/amount
   - 偏差 >0.5% 写入 `data_quality_alerts` 表
   - 偏差 >5% 触发 Slack 告警
2. **复权对齐**
   - 所有源统一用 `adj_factor`（投资数据为准，eltdx 为辅）做前复权和后复权
   - 不同源的 adj_factor 必须一致，否则报警
3. **新股 / 退市 / 停牌处理**
   - 上市首日数据由 baseline 源（investment_data）权威
   - 停牌日不写入主表，仅记录在 `stock_suspension` 表
   - 退市日及之后的数据从查询接口屏蔽
4. **数据回填**
   - 主源历史数据缺失时，自动从备用源回填 + 标记 `source_secondary=true`
   - 回填差异记录在 `data_backfill_log`

### 3.3 异常表

```sql
CREATE TABLE data_quality_alerts (
    id BIGSERIAL PRIMARY KEY,
    trade_date DATE NOT NULL,
    market VARCHAR(8) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    field VARCHAR(32) NOT NULL,
    severity VARCHAR(16),                  -- info / warning / critical
    rule VARCHAR(32),                      -- range / outlier / consensus / adj_mismatch
    source_a VARCHAR(32), value_a NUMERIC,
    source_b VARCHAR(32), value_b NUMERIC,
    diff_pct NUMERIC,
    detail JSONB,
    resolved BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON data_quality_alerts (trade_date DESC, market, severity);
CREATE INDEX ON data_quality_alerts (symbol, field);
```

---

## 4. 交易日历服务 TradingCalendar（新增，每市场独立）

### 4.1 必须解决的问题
- A 股 / 港股 / 美股 节假日不同，**绝不可用一套日历**
- 每市场有不同的开闭盘时间 + 半日（例：HK 圣诞前一天提前收，US 黑色星期五半日）
- cron 任务必须按市场判定 "今天是否交易日"，否则会跑出脏数据 / 浪费资源

### 4.2 数据来源
| 市场 | 主源 | 备用 | 更新频率 |
|---|---|---|---|
| A 股 (SSE/SZSE/BSE) | `chinese_calendar` PyPI + `baostock.query_trade_dates` | `eltdx` | 年度（前年底发布次年） |
| 港股 (HKEX) | `yfinance` + HKEX 官网 ICS | `akshare.tool_trade_date_hist_sina` | 年度 |
| 美股 (NYSE/NASDAQ) | `pandas_market_calendars` PyPI | `yfinance` | 年度 |

### 4.3 表与服务

```sql
CREATE TABLE trading_calendar (
    market VARCHAR(8) NOT NULL,            -- A / HK / US
    trade_date DATE NOT NULL,
    is_trading_day BOOLEAN NOT NULL,
    is_half_day BOOLEAN DEFAULT false,
    open_time TIME,                        -- 当地时间，如 A=09:30, US=09:30 EST
    close_time TIME,
    morning_close TIME,                    -- A 股午间休市，HK 同
    afternoon_open TIME,
    timezone VARCHAR(32),                  -- Asia/Shanghai / Asia/Hong_Kong / America/New_York
    note TEXT,
    PRIMARY KEY (market, trade_date)
);
```

```python
class TradingCalendar:
    def is_trading_day(self, market: str, dt: date) -> bool: ...
    def next_trading_day(self, market: str, dt: date) -> date: ...
    def prev_trading_day(self, market: str, dt: date) -> date: ...
    def get_session(self, market: str, dt: date) -> dict:
        """{ open, morning_close, afternoon_open, close, is_half_day, tz }"""
    def market_status(self, market: str) -> str:
        """pre_open | morning | lunch | afternoon | closed | holiday"""
```

### 4.4 所有 cron 必须改造

现有 cron（如 `sync_investment_data`）改造为：
```python
@cron("0 16 * * 1-5")
def daily_sync_a_stock():
    today = date.today()
    if not calendar.is_trading_day('A', today):
        logger.info(f"[A] {today} 非交易日，跳过同步")
        return
    ...
```

每市场独立 cron：
- A 股：北京时间 16:00 / 17:00（收盘后）
- 港股：北京时间 17:00 / 18:00
- 美股：北京时间次日 06:00 / 07:00（美东收盘 16:00 EST = 北京时间次日 05:00）

---

## 5. 实时 / 分钟 / 订单流（新增 3 层）

### 5.1 数据分层

| Tier | 数据类型 | 频率 | 存储 | 接入源 |
|---|---|---|---|---|
| T1 离线 | 日/周/月 K + 财报 + 公告 | 收盘批量 | Parquet + Qlib bin + PG | investment_data / yfinance / simonlin / ... |
| T2 准实时 | 分钟 K (1/5/15/30/60m) | 每分钟 | Parquet + Redis | eltdx / mootdx / yfinance |
| T3 实时 | 报价 (5档盘口) | 推送 (≤3s) | Redis Stream | eltdx / tdx_api / tencent / simonlin |
| T4 逐笔 | tick / 订单流 | 推送 (毫秒级) | Redis Stream + Kafka(可选) | eltdx / tdx_api |
| T5 资金流 | 主力/大单/中单/小单 | 每分钟聚合 | Parquet + PG | simonlin / efinance |

### 5.2 实时层架构

```
        ┌────────────────────────────────────────────────┐
        │   实时引擎 RealtimeEngine（新进程，独立端口）   │
        │                                                │
        │  ┌──────────────┐    ┌────────────────────┐  │
        │  │ Source Pool  │───▶│  统一格式标准化     │  │
        │  │ eltdx ws     │    │  + 清洗（L1+L2）    │  │
        │  │ tencent http │    └─────────┬──────────┘  │
        │  │ tdx tcp      │              │              │
        │  └──────────────┘              ▼              │
        │                      ┌─────────────────────┐  │
        │                      │  Redis Stream       │  │
        │                      │  quote:A:000001     │  │
        │                      │  tick:A:000001      │  │
        │                      │  flow:A:000001      │  │
        │                      └──────────┬──────────┘  │
        └─────────────────────────────────┼─────────────┘
                                          │
        ┌─────────────────────────────────▼─────────────┐
        │  现有 Stream 服务 (port 8003) WebSocket 推前端 │
        └───────────────────────────────────────────────┘
```

### 5.3 订单流 / 主力资金

- T4 逐笔成交：`eltdx` / `tdx-api` 直接订阅，写 Redis Stream（保留最近 6 小时）
- T5 主力资金：每分钟聚合 `flow_minute:A:000001`，参考 `simonlin/a-stock-data` 的 `push2` 分类（主力 / 大单 / 中单 / 小单）
- 实时订单簿快照：每 3 秒落 PG 一次（写表 `orderbook_snapshot`，分区按日）

---

## 6. 适配器全集（按市场分组）

### 6.1 A 股（10 个源）
| 源 | 字段覆盖 | 实时 | 备注 |
|---|---|---|---|
| `investment_data` (chenditc) | 日线 + 复权 | ❌ | 每日自动更新，qlib-ready，**日线主源** |
| `baostock` | 日/周/月 + 财报 + 复权 | ❌ | A 股老牌稳定 |
| `efinance` | 全市场 + 期货 + 板块 | 部分 | A 股最全 |
| `qstock` | 选股 + RPS + MM + 财务 + 资金 | ❌ | 同花顺选股 |
| `eltdx` | 实时快照/分时/逐笔/K线/竞价/股本/复权 | ✅ | 通达信协议，**实时主源** |
| `tdx-api` (oficcejo) | 同上（HTTP API + Docker） | ✅ | eltdx 互备 |
| `injoyai/tdx` | 通达信协议增强 | ✅ | 备用 |
| `simonlin/a-stock-data` | 行情 + 研报 + 信号 + 资金 + 新闻 + 公告 | 部分 | **F10/财报/龙虎榜/资金流 主源** |
| `mootdx` | K 线 + 五档 + PE/PB + 指数/ETF + 公告 | 部分 | 备用 |
| `akshare` | 全市场通用 | 部分 | 兜底 |

### 6.2 港股（4 个源）
| 源 | 字段覆盖 | 实时 | 备注 |
|---|---|---|---|
| `yfinance` | 日/周/月 + 财报 | ❌ | **日线主源** |
| `simonlin/global-stock-data` | 实时 25-78 字段 + 财报 + 技术指标 | ✅ | **实时/F10 主源** |
| `akshare` | 通用 | 部分 | 备用 |
| `tencent r_hk` | 实时报价 | ✅ | simonlin 备用 |

### 6.3 美股（3 个源）
| 源 | 字段覆盖 | 实时 | 备注 |
|---|---|---|---|
| `simonlin/global-stock-data` | 日线(1984+) + 财报 + SEC XBRL + 期权 + 资金 + 机构持仓 | ✅ | **全字段主源** |
| `yfinance` | 全套 | 部分 | 备用 + 验证 |
| `sec_edgar` 直连 | 10-K/10-Q/8-K + 503 GAAP | ❌ | simonlin 已封装，独立留接口 |

---

## 7. 存储层（同 v1，再补一层）

```
/opt/quantmind/db/
├── qlib_data/
│   ├── cn_data/      # A 股 Qlib bin
│   ├── hk_data/      # 港股 Qlib bin（Phase 4 启用）
│   └── us_data/      # 美股 Qlib bin（Phase 4 启用）
├── parquet/
│   ├── {source}/{market}/{field}/{year}/{symbol}.parquet
│   └── 例：investment_data/A/daily_kline/2026/000001.parquet
│         simonlin_global/US/sec_filing/2026/AAPL_10K.parquet
├── feature_snapshots/
├── realtime/                          # 新增
│   ├── orderbook/{market}/{date}/    # 订单簿快照
│   └── tick/{market}/{date}/         # 逐笔归档（每日压缩冷归档）
└── calendars/                         # 新增
    └── {market}.parquet               # 各市场交易日历缓存
```

---

## 8. 监控层 HealthMonitor（升级）

每个 **(source, field)** 维度记录：
- last_success_at / last_error_at / last_error_msg
- rows_today / rows_yesterday
- avg_latency_ms / p95_latency_ms
- error_rate_1h / error_rate_24h
- fallback_triggered_count（被降级到备用源的次数）
- consensus_deviation_avg（多源一致性偏差均值）

Redis key：`quantmind:datasource:health:{source}:{field}`

后台 UI：
- 「数据源监控」总览：每源一张卡 + 总体绿/黄/红
- 「字段覆盖矩阵」：market × field × source 的三维矩阵，鼠标悬停看健康
- 「数据质量报告」：data_quality_alerts 按日 / 市场 / 严重度筛选
- 「实时流监控」：T3/T4 流的 lag / qps / 断连次数

---

## 9. 反爬 / 限流 / 成本

| 风险 | 缓解 |
|---|---|
| 同花顺 / 东财抓取被封 | adapter 内置最小间隔（同花顺 5s/东财 2s）、Redis 缓存、proxy 池（先留接口） |
| Yahoo / SEC 限流 | crumb 缓存、User-Agent 轮换、夜间错峰 |
| 通达信服务器抖动 | eltdx/tdx 多服务器列表轮询、健康探测 |
| 实时流断连 | 自动重连 + 指数退避 + Redis Stream 保留窗口（≥6h）做断点续传 |
| 磁盘膨胀 | Parquet 用 Zstd-3 压缩；tick 数据 90 天后归档冷盘；订单簿 30 天后只保留每小时快照 |
| 全市场并行抓取撑爆内存 | 按市场串行 + Celery 队列 concurrency=1 |
| GitHub 上的源代码更新 | 用 git submodule 锁版本 + 季度评审升级 |

---

## 10. 里程碑（v2 重排）

| Sprint | 工作量 | 内容 |
|---|---|---|
| **S1 基础设施**（2 天） | 抽象层 + 字段路由 + 清洗框架 + 交易日历 + 监控骨架 |
| **S2 A 股全量接入**（3 天） | 10 个 A 股源全部接入 + 路由配好 + 校验跑通 |
| **S3 港美股接入**（2 天） | yfinance + simonlin_global + akshare + sec_edgar |
| **S4 实时流**（3 天） | 实时引擎进程 + Redis Stream + 5档盘口 + 逐笔 + 资金流 |
| **S5 前端**（3 天） | 数据源监控页 + 字段覆盖矩阵 + 数据质量页 + K线组件（lightweight-charts）+ 市场切换 |
| **S6 校验 / 准确率**（2 天） | 多源一致性 cron + 抽样校验 + 复权对齐 + 告警通道 |
| **S7 联调 + 灰度**（2 天） | 端到端 + 限流策略 + 监控指标兜底 + 故障切换演练 |
| **合计** | **约 17 个工作日（≈ 3.5 周）** | 完整交付 |

---

## 11. 不在本规划内（明确剔除）

- **Qlib 多市场 region**（HK/US 进 Qlib bin）— Phase 4，需 Qlib 内核改动
- **AI 自动选源策略**（机器学习选最优源）— 远期
- **机房级冗余**（多区域 Redis Sentinel）— 部署侧，不在数据平台

---

## 12. 决策点（请确认）

1. **17 天工作量能否接受？** 是否希望先出 MVP（S1+S2+S5 ≈ 8 天）让 A 股先完整跑起来，再继续港美股/实时？
2. **告警通道**：data_quality_alerts critical 级别发到哪？（Slack / 企微 / 邮件 / 站内通知）
3. **实时数据是否走 Kafka**？目前规划只用 Redis Stream，省运维。如果将来 QPS 上万再加 Kafka。
4. **接入这些源时是否用 git submodule**？建议是 — 各源版本可控、可回退。
