# Strategy Lab 完整规范

> 本文档为 QuantMind「策略实验室」(Strategy Lab) 模块的完整设计规范。
>
> **版本**：v1.0 · 规划态
> **作者**：QuantMind Dev
> **更新日期**：2026-06-12
> **目标**：为后续 19 天开发提供单一信源 (Single Source of Truth)。

---

## 1. 产品定位与边界

### 1.1 一句话定位

> 浏览器版 **TradingView × Jupyter × 量化沙盒**——左 AI 写代码、中跑回测、右看 K 线。
> **纯本地数据 + 纯 Python + 不强制大模型**。

### 1.2 与现有模块的边界

| 模块 | 干啥 | 与 Strategy Lab 的关系 |
|---|---|---|
| 「策略向导」`/strategy-wizard` | 选模板 → 配参数 → 跑 TopK 回测 | 固定范式产品，**互补** |
| 「AI-IDE」`/ai-ide` | 写后端工程代码、调试 | 工程师视角，**底层复用其聊天/编辑器** |
| 「Alpha 研究」`/alpha-research` | 152 维特征查询、因子可视化 | **跳转复用**，不重做 |
| 「回测中心」`BacktestCenter` | 平台模板回测、历史、对比 | **共表 `qm_backtest_runs`** |
| **Strategy Lab** ✨ | 写**想法 → 跑 → 看 K 线买卖点 → 改 → 再跑** | 围绕"研究一个策略想法"组织界面 |

### 1.3 核心价值差异化

> 本地 Python + 本地数据 + Qlib 引擎 + AI 写代码 + TradingView 风格 K 线
>
> **此组合在市面无第二份**，构成核心护城河。

| 友商 | 弱项 |
|---|---|
| TradingView | 没本地数据、没 Python |
| Backtrader / Zipline | 没 UI |
| 聚宽 / 米筐 | SaaS 收费、不可定制 |
| QMT / Ptrade | 门槛高、桌面客户端 |

---

## 2. 用户工作流

### 2.1 核心闭环

```
①点片段 / 让AI写  →  ②微调  →  ③▶运行
       ↑                                ↓
       │                                │
       └← ⑤改代码 ← ④右栏看 K 线买卖点 + 净值 + 持仓 ←
```

**KPI**：典型用户 **5 分钟内** 完成"听说 RSI<30 反弹有戏 → 让 AI 写代码 → 跑回测 → 看买卖点 → 加止盈 15% → 再跑 → 收益翻倍"全闭环。

### 2.2 高频场景

| # | 场景 | 路径 |
|---|---|---|
| 1 | 验证一个新策略想法 | 片段库 → 改参数 → 运行 → 看 K 线 |
| 2 | 找 AI 帮写公式选股 | AI 助手对话 → 接受 diff → 运行 |
| 3 | 看自己历史策略效果 | 历史 Tab → 选策略 → 加载 |
| 4 | 跨策略对比 | 跑 A → 跑 B → "vs 上一版" |
| 5 | 找过拟合 | 跑回测 → 4 关卡报告 → 看红字警告 |
| 6 | 把策略转上实盘 | 4 关卡通过 → "转模板" → 进 strategy-wizard |

---

## 3. 整体界面布局

### 3.1 主布局

```
┌──────────────────────────────────────────────────────────────────────────┐
│  顶栏：📁 策略名  ▶ 运行  ⏹ 停止  💾 保存  📤 转模板  🔍 vs上一版  ⚙ 设置 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│ ┌────────────┬──────────────────────────────┬───────────────────────┐   │
│ │            │                              │                       │   │
│ │  🤖 AI助手  │      📝 代码 (Monaco)        │   📈 K线 + 交易点     │   │
│ │  片段库:    │                              │  ┌─────────────────┐  │   │
│ │  - v3斐波   │  def setup(ctx):             │  │ 600519.SH       │  │   │
│ │  - 双均线   │      ctx.universe='csi300'   │  │  ╲╱╲╱╱╲ ▲▼      │  │   │
│ │  - 布林带   │      ctx.cash=1_000_000      │  │ 5min/30min/Day  │  │   │
│ │  - 行业轮动 │                              │  │ S1线/R1线 overlay│ │   │
│ │  - PEG选股  │  def on_bar(ctx, bar):       │  │ 显示:开仓/止盈/  │  │   │
│ │  - 五行选股 │      if bar.close < ...      │  │ 止损/支撑/压力  │  │   │
│ │            │          ctx.buy(bar.symbol) │  └─────────────────┘  │   │
│ │  对话区:    │                              │                       │   │
│ │  > 帮我加   │                              │  ┌─────────────────┐  │   │
│ │   止损     │                              │  │ 📊 净值曲线     │  │   │
│ │  [实时diff │                              │  │ ─── 策略 ╴╴ 基准│  │   │
│ │   ✓接受 ✗] │                              │  │ Sharpe 1.2 DD-15│ │   │
│ │            │                              │  └─────────────────┘  │   │
│ └────────────┴──────────────────────────────┴───────────────────────┘   │
│                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │ 底部 Tab：交易明细 | 持仓 | 资金曲线 | 月度热力 | 评分卡 | 数据字典  │ │
│ │  ────────────────────────────────────────────────────────────────  │ │
│ │  日期       股票      方向  价格    数量   原因           盈亏    │ │
│ │  2024-03-15 600519   BUY  1820.50  100   触发S2(0.618)  ──     │ │
│ │  2024-04-20 600519   SELL 1965.00  100   触发R1(1.236)  +7.9%  │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 布局规则

- **三栏宽度可拖拽**：默认 `15% / 50% / 35%`，最小 `200/400/300`
- **底部 Tab 抽屉**：可上下拖拽，最高占 60% 视口高度，支持折叠
- **AI 助手抽屉**：默认开，可一键收起到右侧悬浮按钮
- **主题**：复用 AIIDE 暗色主题，保持视觉一致性
- **响应式断点**：< 1280px 折叠 AI 助手为悬浮抽屉；< 1024px 提示"建议大屏使用"

### 3.3 路由

```
/strategy-lab                    主页面（新建/默认空白）
/strategy-lab/:script_id         打开已保存的脚本
/strategy-lab/run/:run_id        分享一次回测结果（v2 加 share token）
```

App.tsx 加路由：

```tsx
<Route path="/strategy-lab/*" element={<StrategyLabPage />} />
```

侧边栏菜单 `'strategy-lab': '/strategy-lab'` 与 `'ai-ide': '/ai-ide'` 同级。

---

## 4. 策略 SDK 规范

### 4.1 设计原则

1. **人类可读** > 全功能。AI 写代码先要保证人能看懂、能改
2. **不暴露 Qlib 内部对象**（`Order`、`OrderDir`、`TradeDecisionWO`），平台底层翻译
3. **单文件单策略**，禁止复杂工程结构
4. **三个钩子覆盖 95% 场景**：`setup` / `on_bar` / `on_universe`
5. **失败友好**：缺字段、错类型、未来函数都给行号 + 修改建议

### 4.2 标准模板

```python
# ============ 标准 Strategy Lab 脚本骨架 =============

def setup(ctx):
    """初始化（一次性）：声明池子、初始资金、调仓节奏、参数"""
    # ── 必填 ──
    ctx.universe   = 'csi300'           # 股票池
    ctx.start      = '2020-01-01'
    ctx.end        = '2025-12-31'
    ctx.cash       = 1_000_000          # 初始资金（元）
    ctx.benchmark  = 'SH000300'

    # ── 选填（默认即合规）──
    ctx.commission = 0.0003             # 万三
    ctx.slippage   = 0.0005             # 万五
    ctx.tax_sell   = 0.0005             # 印花税卖单 0.05%（2023+）
    ctx.transfer_fee = 0.00001          # 过户费 0.001%
    ctx.execution_model = 'a_share_strict'  # T+1 + 涨跌停 + 次开成交
    ctx.max_position_per_stock = 0.10
    ctx.max_positions = 10
    ctx.engine = 'qlib'                 # v1 仅 Qlib

    # ── 可声明扫描参数 ──
    ctx.param('window', range(10, 50, 5), default=22)
    ctx.param('stop_loss', [0.05, 0.08, 0.10, 0.15], default=0.10)


def on_universe(ctx, date, snapshot):
    """每日开盘前调用一次，做横截面选股。
    - date: pd.Timestamp 当前交易日
    - snapshot: DataFrame, index=symbol, cols=['open','high','low','close','volume',
      'pe','pb','roe','momentum_20', ...152 维特征]
    可选实现。返回 None 表示沿用昨日选股。
    """
    picks = (
        snapshot
        .query("pe < 15 and roe > 0.15")
        .nlargest(10, 'momentum_20')
        .index.tolist()
    )
    ctx.set_target_holdings(picks, weight='equal',
                            reason='value+momentum_top10')


def on_bar(ctx, bar):
    """单股每根 K 线调用一次。
    - bar.symbol/date/open/high/low/close/volume
    - bar.adj_close（后复权）
    - bar.feature('momentum_20') 取 152 维特征
    """
    sym = bar.symbol
    closes = ctx.history(sym, n=22, field='close')
    if len(closes) < 22:
        return

    high22 = closes.max()
    low22  = ctx.history(sym, n=22, field='low').min()
    s1 = high22 * 0.786

    if not ctx.position(sym).qty and abs(bar.close - s1) / s1 < 0.03:
        ctx.buy(sym, weight=0.05,
                reason='S1_hit',
                detail={'close': bar.close, 's1': s1, 'pct': abs(bar.close - s1) / s1})
        ctx.set_stop_loss(sym, -0.10)
        ctx.set_take_profit(sym, 0.15)


def on_finish(ctx):
    """回测结束钩子（可选）。"""
    ctx.log(f"策略结束，共 {ctx.stats.n_trades} 笔交易")
```

### 4.3 Context API 完整清单

#### 4.3.1 配置

| 属性 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `universe` | str / List[str] | 必填 | `csi300` / `csi500` / `all_a` / `hk_main` / `us_sp500` / 自定义列表 |
| `start` / `end` | str | 必填 | YYYY-MM-DD |
| `cash` | float | 必填 | 初始资金 |
| `benchmark` | str | `SH000300` | 基准 |
| `commission` | float | 0.0003 | 双向手续费率 |
| `slippage` | float | 0.0005 | 双向滑点 |
| `tax_sell` | float | 0.0005 | 印花税（仅卖单） |
| `transfer_fee` | float | 0.00001 | 过户费（双向） |
| `execution_model` | str | `a_share_strict` | `a_share_strict` / `simple` |
| `max_position_per_stock` | float | 0.10 | 单股最大仓位 |
| `max_positions` | int | 10 | 同时持仓股票数 |
| `engine` | str | `qlib` | 暂只支持 `qlib` |

#### 4.3.2 数据访问

```python
# 历史数据
ctx.history(symbol, n=20, field='close')              # 单股近 N 根某字段
ctx.history(symbol, n=20, fields=['open','high'])     # 多字段
ctx.history(symbols=[...], n=20, field='close')       # 多股拼成 DataFrame

# 因子访问（152 维 parquet）
ctx.feature(symbol, name='momentum_20')               # 当前最新值
ctx.feature(symbol, name='momentum_20', n=10)         # 历史 N 根
ctx.list_features()                                   # 列出可用因子

# 行情快照
ctx.snapshot(date)                                    # 全市场某日 OHLCV
ctx.snapshot(date, symbols=[...])                     # 限定股票

# 基准
ctx.benchmark_history(n=20)
```

#### 4.3.3 下单

```python
ctx.buy(symbol, weight=0.05, reason='', detail={})           # 按目标权重买入
ctx.buy(symbol, qty=100, reason='')                          # 按股数买入
ctx.sell(symbol, weight=0.05, reason='')                     # 按权重卖出
ctx.sell(symbol, all=True, reason='')                        # 全部卖出
ctx.set_position(symbol, weight=0.05, reason='')             # 直接设到目标仓位
ctx.set_target_holdings([sym1, sym2], weight='equal',        # 横截面调仓
                        reason='')
```

> **要点**：所有下单方法都接受 `reason`（字符串）+ `detail`（dict），用于 Why 解释器。

#### 4.3.4 风控

```python
ctx.set_stop_loss(symbol, pct=-0.10)                  # 单股止损（相对成本）
ctx.set_take_profit(symbol, pct=0.15)                 # 单股止盈
ctx.set_account_stop_loss(pct=-0.20)                  # 账户级止损（净值）
ctx.set_max_holding_days(symbol, days=30)             # 最大持有天数
```

#### 4.3.5 持仓查询

```python
ctx.position(symbol)            # 单股持仓
  .qty           股数
  .cost          持仓成本（含买入费用）
  .market_value  市值
  .pnl           浮盈
  .pnl_pct       浮盈率
  .holding_days  持有天数
  .reason        买入原因（来自 buy 时的 reason）

ctx.positions()                 # 所有持仓 DataFrame
ctx.cash                        # 当前可用现金
ctx.equity                      # 当前总权益
```

#### 4.3.6 工具

```python
ctx.log(msg, level='info')      # 日志（出现在结果区"日志"Tab）
ctx.plot_line(name, value)      # 在 K 线上画指标线（如支撑位）
ctx.plot_marker(symbol, type='alert', text='')  # 自定义 marker
ctx.param(name, choices, default)  # 声明扫描参数

# 内置工具
ctx.is_st(symbol)               # 是否 ST
ctx.is_tradable(symbol)         # 今天可交易吗（涨跌停 / 停牌过滤）
ctx.industry(symbol)            # 申万一级行业
ctx.market_cap(symbol)          # 市值
```

### 4.4 SDK 禁用清单（沙盒规则）

```python
# ❌ 禁止
import os, sys, subprocess, socket, ctypes, importlib
open(file, 'w'); open(file, 'a')
exec(...); eval(...)
__import__(...)

# ✅ 允许
import numpy, pandas, scipy, math, statistics, itertools
import datetime, json, re, collections
import talib  # 技术指标库
# 任何不触发文件 IO / 网络 / 子进程的纯计算
```

实现方式：AST 静态白名单 + subprocess seccomp 兜底（详见 §7）。

---

## 5. 后端架构

### 5.1 模块树

```
backend/services/engine/strategy_lab/
├── __init__.py
├── routers.py                  # FastAPI 路由（8 个接口）
├── sdk/
│   ├── context.py              # Context 类
│   ├── bar.py                  # Bar 类（OHLCV + features）
│   ├── position.py             # Position 类
│   └── data_dict.py            # 字段元数据
├── runner/
│   ├── ast_checker.py          # AST 白名单
│   ├── subprocess_runner.py    # 复用 ai_ide/executor.py 的子进程框架
│   ├── progress.py             # 进度推送（SSE）
│   └── result_collector.py     # 结果聚合
├── engine/
│   ├── qlib_adapter.py         # SDK → Qlib backtest
│   ├── execution_model.py      # 成交模型（A股严格 / simple）
│   └── translator.py           # SDK → RedisFreeFormStrategy 翻译器
├── overfit/
│   ├── train_test_split.py     # 关卡 1
│   ├── walk_forward.py         # 关卡 2
│   ├── sensitivity.py          # 关卡 3
│   ├── monte_carlo.py          # 关卡 4
│   └── score_card.py           # 评分卡
├── snippets/
│   └── builtin/                # 30 个内置示例（v3 斐波等）
└── cron/
    └── daily_scan.py           # 每日扫描已保存策略

backend/services/engine/qlib_app/utils/extended_strategies.py
└── + RedisFreeFormStrategy     # 新增（~250 行）
```

### 5.2 接口清单

| 接口 | 方法 | 用途 |
|---|---|---|
| `/strategy-lab/run` | POST | 同步回测（< 30s 自动判断） |
| `/strategy-lab/run/async` | POST | 异步回测，返回 `task_id` |
| `/strategy-lab/run/{id}/status` | GET (SSE) | 进度推送 |
| `/strategy-lab/run/{id}/result` | GET | 拉取完整结果 |
| `/strategy-lab/kline-with-trades` | GET | K 线 + 该次回测的交易点 |
| `/strategy-lab/snippets` | GET | 30 个内置 + 我的脚本 |
| `/strategy-lab/snippets` | POST | 保存我的脚本 |
| `/strategy-lab/snippets/{id}` | DELETE | 删除我的脚本 |
| `/strategy-lab/data-dict` | GET | 152 维字段元数据（hover 提示用） |
| `/strategy-lab/chat` | POST (SSE) | 透传 ai_ide/chat，注入 Lab 系统提示词 |
| `/strategy-lab/translate-to-template` | POST | SDK → 平台模板 |
| `/strategy-lab/overfit-check` | POST | 跑 4 关卡 |
| `/strategy-lab/param-scan` | POST | 参数扫描 |
| `/strategy-lab/compare` | POST | 两次回测对比 |

### 5.3 数据契约

#### 5.3.1 RunRequest

```json
{
  "code": "def setup(ctx): ...",
  "params": { "window": 22, "stop_loss": 0.10 },
  "options": {
    "engine": "qlib",
    "save_to_history": true
  }
}
```

#### 5.3.2 RunResult

```json
{
  "run_id": "lab_2026061201_abc123",
  "status": "success | failed | running",
  "metrics": {
    "cum_return": 0.158,
    "annual_return": 0.031,
    "sharpe": 0.372,
    "max_drawdown": -0.169,
    "win_rate": 0.55,
    "n_trades": 42,
    "avg_position": 0.32
  },
  "equity": [
    {"date": "2021-01-04", "value": 1000000, "benchmark": 5000.5}
  ],
  "trades": [
    {
      "date": "2024-03-15",
      "symbol": "SH600519",
      "direction": "BUY",
      "price": 1820.50,
      "qty": 100,
      "reason": "S1_hit",
      "detail": {"close": 1820, "s1": 1810},
      "pnl": null
    }
  ],
  "positions": [
    {"date": "2024-03-15", "symbol": "SH600519", "qty": 100,
     "cost": 1820.50, "market_value": 182050, "pnl_pct": 0}
  ],
  "overlays": {
    "SH600519": [
      {"name": "S1", "color": "red", "style": "dashed",
       "values": [{"date": "...", "value": 1810}, ...]}
    ]
  },
  "logs": ["..."],
  "score_card": {
    "total": 67,
    "breakdown": [
      {"item": "Sharpe 1.2", "score": 25, "type": "good"},
      {"item": "最大回撤 -28%", "score": -15, "type": "warning"},
      {"item": "训练vs测试Sharpe差0.8", "score": -13, "type": "danger"}
    ]
  },
  "warnings": [
    "数据 csi300 在 2010-01 之前不存在",
    "factor X 在 2018-01 之前为 NaN"
  ],
  "data_snapshot_at": "2026-06-12T10:00:00Z",
  "script_sha": "abc123def456",
  "elapsed_sec": 47.3
}
```

### 5.4 数据库表（增 / 改）

#### 5.4.1 复用 `qm_backtest_runs`（已有）

新增字段：

```sql
ALTER TABLE qm_backtest_runs
  ADD COLUMN source VARCHAR(32) DEFAULT 'platform',  -- platform / strategy_lab
  ADD COLUMN script_sha VARCHAR(64),
  ADD COLUMN data_snapshot_at TIMESTAMPTZ,
  ADD COLUMN parent_run_id VARCHAR(64);              -- vs上一版用
CREATE INDEX idx_qm_backtest_runs_source ON qm_backtest_runs(source, user_id);
```

#### 5.4.2 新表 `qm_lab_scripts`

```sql
CREATE TABLE qm_lab_scripts (
  id BIGSERIAL PRIMARY KEY,
  script_id VARCHAR(64) UNIQUE NOT NULL,
  user_id BIGINT NOT NULL,
  name VARCHAR(200) NOT NULL,
  description TEXT,
  code TEXT NOT NULL,
  params JSONB DEFAULT '{}',
  visibility VARCHAR(16) DEFAULT 'private',  -- private / shared / public（v2）
  daily_scan_enabled BOOLEAN DEFAULT FALSE,
  tags VARCHAR(255)[],
  latest_run_id VARCHAR(64),
  latest_score INT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_qm_lab_scripts_user_id ON qm_lab_scripts(user_id);
CREATE INDEX idx_qm_lab_scripts_daily_scan ON qm_lab_scripts(daily_scan_enabled) WHERE daily_scan_enabled;
```

#### 5.4.3 新表 `qm_lab_signals`（每日扫描产出）

```sql
CREATE TABLE qm_lab_signals (
  id BIGSERIAL PRIMARY KEY,
  script_id VARCHAR(64) NOT NULL,
  user_id BIGINT NOT NULL,
  scan_date DATE NOT NULL,
  symbol VARCHAR(16) NOT NULL,
  direction VARCHAR(8) NOT NULL,    -- BUY / SELL
  reason VARCHAR(64),
  detail JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (script_id, scan_date, symbol, direction)
);
CREATE INDEX idx_qm_lab_signals_user_date ON qm_lab_signals(user_id, scan_date DESC);
```

### 5.5 可重复性保障

每次 run 入库时记录：

- `script_sha` = SHA256(code + sorted(params))
- `data_snapshot_at` = qlib 数据最后更新时间（读 `qlib_data/calendars/day.txt` 末行）
- `qlib_version` = 当时的 Qlib 版本
- `python_version` / 关键依赖 hash

3 个月后重跑、SHA + 数据时间戳一致 → 结果必须一致（误差 < 1e-6）。

---

## 6. 前端架构

### 6.1 模块树

```
electron/src/features/strategy-lab/
├── pages/
│   └── StrategyLabPage.tsx       # 主页面
├── components/
│   ├── layout/
│   │   ├── ThreeColumnLayout.tsx # 三栏拖拽
│   │   └── BottomDrawer.tsx      # 底部 Tab 抽屉
│   ├── editor/
│   │   ├── CodeEditor.tsx        # Monaco 包装（复用 AIIDE）
│   │   ├── HoverProvider.tsx     # 字段元数据 hover
│   │   └── DiffPreview.tsx       # AI 改代码预览
│   ├── ai/
│   │   ├── AIChatPanel.tsx       # 复用 AIIDE ChatPanel（抽组件）
│   │   ├── PromptLibrary.tsx     # 30 个示例
│   │   └── DiffAcceptReject.tsx
│   ├── kline/
│   │   ├── EnhancedKlineChart.tsx  # 包 KlineChart + markers + overlays
│   │   ├── TradeMarker.tsx
│   │   ├── DrawnLineTool.tsx     # 手画线（v1.5）
│   │   └── WhyExplainModal.tsx
│   ├── result/
│   │   ├── EquityCurve.tsx       # 复用 EnhancedQuickBacktest 抽出
│   │   ├── KpiCards.tsx
│   │   ├── MonthlyHeatmap.tsx
│   │   ├── PositionTable.tsx
│   │   ├── TradeTable.tsx
│   │   ├── ScoreCard.tsx
│   │   ├── OverfitReport.tsx
│   │   └── ParamScanHeatmap.tsx
│   ├── compare/
│   │   └── VsLastVersionPanel.tsx
│   └── progress/
│       └── ProgressBar.tsx
├── services/
│   ├── strategyLabService.ts
│   ├── snippetService.ts
│   └── chatService.ts
├── store/
│   └── strategyLabSlice.ts
└── types/
    ├── sdk.ts
    └── result.ts
```

### 6.2 复用清单（关键省工）

| 需求 | 复用源 | 复用方式 |
|---|---|---|
| Monaco 编辑器 | `pages/AIIDEPage.tsx` | 抽出 `<CodeEditor>` 组件 |
| AI 聊天 SSE | `pages/AIIDEPage.tsx` | 抽出 `<AIChatPanel context>` |
| K 线渲染 | `components/KlineChart.tsx` | 加 `markers` + `overlays` props |
| 净值曲线 | `components/backtestCenter/EnhancedQuickBacktest.tsx` | 抽出 `<EquityCurve>` |
| KPI 卡 | 同上 | 抽出 `<KpiCards>` |
| 策略对比 | `components/backtestCenter/StrategyComparisonModule.tsx` | 嵌入 vs上一版 |
| 历史回测 | `components/backtestCenter/BacktestHistoryModule.tsx` | 加 `source=strategy_lab` 过滤 |
| 参数优化 | `components/backtestCenter/ParameterOptimizationModule.tsx` | 接 SDK `ctx.param()` |
| 行业暴露 | `components/backtestCenter/EnhancedAdvancedAnalysisModule.tsx` | 直嵌 |
| 152 维特征 | `features/alpha-research` | 跳转链接 |

> **预计**：复用让前端工作量减少 30-40%。

### 6.3 状态管理

`strategyLabSlice.ts` 维护：

```ts
interface StrategyLabState {
  // 当前编辑
  scriptId: string | null;        // null = 新建
  code: string;
  params: Record<string, any>;
  dirty: boolean;

  // AI 助手
  chatHistory: ChatMessage[];
  pendingDiff: { oldCode: string; newCode: string } | null;

  // 当前回测
  runId: string | null;
  runStatus: 'idle' | 'running' | 'success' | 'failed';
  progress: { stage: string; pct: number };
  result: RunResult | null;

  // 对比
  baseRunId: string | null;       // vs 上一版

  // UI
  activeBottomTab: 'trades' | 'positions' | 'equity' | ... ;
  selectedSymbol: string | null;  // K线显示哪只
  klineRange: [string, string];
}
```

---

## 7. 安全沙盒

### 7.1 三层防护

```
用户代码
   │
   ▼
┌──────────────────┐
│ Layer 1: AST 白名单 │ 拒绝 import os/sys/subprocess/socket，
│                  │ 拒绝 open with 'w'/'a'，拒绝 exec/eval
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Layer 2: 子进程   │ python -m strategy_lab.runner <script>
│                  │ - 不继承父进程环境变量（DB/Redis 凭证擦除）
│                  │ - 只读挂载 /app/db/qlib_data
│                  │ - cgroup CPU 限 1 核
│                  │ - 内存上限 1 GB
│                  │ - 硬超时 60s（同步）/ 300s（异步）
│                  │ - 临时目录配额 100 MB
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Layer 3: 容器     │ 整个 quantmind 容器已 Docker 隔离，
│                  │ 网络出栈受 docker-compose 限制
└──────────────────┘
```

### 7.2 AST 白名单实现

```python
ALLOWED_MODULES = {
    'numpy', 'pandas', 'scipy', 'math', 'statistics', 'itertools',
    'datetime', 'json', 're', 'collections', 'functools',
    'talib', 'qlib.data',  # 限定子模块
}

FORBIDDEN_NODES = {
    # AST 节点黑名单
    ast.Import: lambda n: any(a.name.split('.')[0] not in ALLOWED_MODULES for a in n.names),
    ast.ImportFrom: lambda n: n.module and n.module.split('.')[0] not in ALLOWED_MODULES,
    # exec / eval / open 调用
    ast.Call: lambda n: isinstance(n.func, ast.Name) and n.func.id in {'exec', 'eval', 'open', '__import__'},
}
```

### 7.3 错误友好化

```python
# 用户写 bar.opn 拼错
# 默认 stack：AttributeError: 'Bar' object has no attribute 'opn'
# 友好化：

第 12 行: bar 没有属性 'opn'
       │
   12  │      if bar.opn > bar.close:
       │             ^^^
       │
建议：是不是想写 bar.open ？
       可用属性：symbol, date, open, high, low, close, volume, adj_close

```

实现：在 runner 里 catch AttributeError，做编辑距离匹配建议。

---

## 8. AI 助手集成

### 8.1 复用 ai_ide/chat.py

不重写，注入新的系统提示词：

```python
# backend/services/engine/routers/ai_ide/skill_templates/strategy_lab.md

你是 QuantMind Strategy Lab 的策略研究员助手。用户问什么，你就用 Python 给代码。

【硬约束】生成的代码必须遵守这套 SDK：
- 入口：def setup(ctx) 一次性配置；def on_bar(ctx, bar) 每只股票每根K线；
        def on_universe(ctx, date, snapshot) 每日横截面（可选）
- 数据：ctx.history(symbol, n=20, field='close')
- 因子：ctx.feature(symbol, 'momentum_20')  支持 152 维 parquet
- 下单：ctx.buy(sym, weight=0.1, reason='') / ctx.sell(sym) /
        ctx.set_target_holdings([syms], weight='equal')
- 风控：ctx.set_stop_loss(sym, -0.10) / ctx.set_take_profit(sym, 0.15)
- 持仓：ctx.position(sym).qty / .cost / .pnl_pct / .holding_days
- 禁止：os/sys/subprocess/socket/open(...,'w')/exec/eval

【数据可用】
- 标的池：csi300 / csi500 / csi800 / hs300_ext / all_a / hk_main / us_sp500
- 频率：day / 30min（5min 仅近 2 年）
- 字段：$open $high $low $close $volume $factor + 152 维特征
  （详见 ctx.list_features() 或调用工具 get_data_dict()）
- 时间范围：2010-01-01 ~ {{TODAY}}

【回测原则】
- 严禁未来函数（只能用 bar.close 当前及之前）
- 严禁前视（因子要 shift(1)）
- 默认 A 股合规模型：T+1、印花税 0.05%、涨跌停过滤、次开成交

【当前上下文】
{{USER_CURRENT_CODE}}
{{LAST_RUN_RESULT_SUMMARY}}

【输出格式】
- 直接给完整可运行代码，不要解释
- 在代码上方一行注释说明思路（≤30字）
- 关键变量加中文注释
- 必须包含 setup + on_bar 或 on_universe
```

### 8.2 上下文注入

每次调用 `/strategy-lab/chat`，自动拼装：

```python
context = {
    'user_current_code': editor.code,
    'last_run_result_summary': summary(latest_run.result),  # KPI 几行
    'universe': ctx.universe,
    'time_range': (ctx.start, ctx.end),
}
```

### 8.3 实时 Diff

```
用户: 帮我加止损 8%
   ↓
AI（流式输出）: ```python
   def setup(ctx):
       ctx.universe = 'csi300'
+      ctx.stop_loss_default = 0.08
       ...
   ```
   ↓
前端实时绿色高亮新增行，红色高亮删除行
   ↓
[✓ 接受]   [✗ 拒绝]   [📝 部分接受]
   ↓
接受 → 直接 patch 编辑器
```

### 8.4 通过率验收（硬指标）

Sprint 1 必跨 30 个标准 prompt 测试集，**通过率 ≥ 60%** 才能进 Sprint 2。

测试集示例：
1. "用 20 日均线金叉买入"
2. "RSI 小于 30 时买入"
3. "选 PE < 15 且 ROE > 15% 的前 10 只"
4. "动量前 20 + 波动率后 20 的股票等权"
5. "支撑位 0.618 倍前期高点附近买入"
6. "MACD 金叉 + 量能放大 1.5 倍"
7. "市值最小的 50 只 + 月度调仓"
8. "PEG < 1 的成长股"
9. "突破 60 日新高且涨停板缩小的"
10. "破净（PB<1）+ ROE 转正"
... (共 30 题)

通过 = 代码能跑通 + 结果合理（信号数 > 0、夏普非 0）。

---

## 9. 防过拟合检测（4 关卡）

### 9.1 关卡设计

| 关卡 | 检查 | 实现 |
|---|---|---|
| **1. 训练/测试分割** | 是否有样本外验证 | 默认 70/30 时序拆分，分别给 KPI，差距 > 50% 红色警报 |
| **2. 走查验证（Walk-Forward）** | 滚动训练/测试是否稳 | 5 折滚动（如 2016-18→19/19-21→22），各折 Sharpe 标准差 |
| **3. 参数敏感度** | 单参数 ±20% 收益稳吗 | 自动跑 ±10%/±20%，绘等高线，悬崖警告 |
| **4. 蒙特卡洛打乱** | 真信号还是运气 | 把买卖日随机重排 1000 次，真策略 Sharpe 应排前 5% |

### 9.2 评分算法

```
total = 100 - sum(deductions)

deductions = [
  ('Sharpe < 0.5', -15 if sharpe < 0.5 else 0),
  ('最大回撤 < -25%', -15 if max_dd < -0.25 else 0),
  ('胜率 < 40%', -10 if win_rate < 0.40 else 0),
  ('交易笔数 < 10', -10 if n_trades < 10 else 0),
  ('集中度过高（前3票贡献>80%）', -10 if top3_contrib > 0.80 else 0),
  ('训测Sharpe差>50%', -15 if abs(sr_train - sr_test) / sr_train > 0.50 else 0),
  ('参数敏感度高（±20%夏普差>0.3）', -10 if param_sens > 0.3 else 0),
  ('蒙特卡洛排名 < 95%', -10 if mc_rank < 0.95 else 0),
  ('数据未来函数嫌疑', -25 if has_future_leak() else 0),
]
```

### 9.3 报告 UI

```
得分 67 / 100  ⚠️ 低于及格线

✅ Sharpe 1.2          (+25)
✅ 胜率 55%             (+15)
⚠️ 最大回撤 -28%         (-15)
⚠️ 仅 3 只样本贡献 80% 收益 (-10)  ← 集中度风险
❌ 训练期 vs 测试期 Sharpe 差 0.8 (-13)  ← 过拟合嫌疑

[ 跑详细 4 关卡报告 ]   [ 接受风险，仍要保存 ]
```

---

## 10. 闭环：转模板上实盘

### 10.1 翻译器架构

```
┌─────────────────┐
│ SDK 脚本         │  setup() + on_bar()
└────────┬────────┘
         ▼
┌─────────────────┐
│ AST 解析         │  抽出 universe, 触发条件, 风控参数
└────────┬────────┘
         ▼
┌─────────────────┐
│ 模板代码生成      │  生成 RedisFreeFormStrategy 子类
└────────┬────────┘
         ▼
┌─────────────────────────────┐
│ 写入 strategy_templates/   │
│   <id>.json + <id>.py      │
│   markets: ["a_share"]     │
└────────┬────────────────────┘
         ▼
   等模板缓存 TTL 过期（60s）
         ▼
   平台「策略向导」可见
```

### 10.2 RedisFreeFormStrategy 设计

新增于 `extended_strategies.py`，~250 行：

```python
class RedisFreeFormStrategy(DynamicRiskMixin, RedisLoggerMixin):
    """事件驱动通用策略（不依赖 PRED 信号）

    被 SDK 翻译器自动生成。每天遍历 universe，
    对每只股票调用 user_on_bar(ctx, bar)；
    （可选）每日开盘前调 user_on_universe(ctx, date, snapshot)。
    """

    def __init__(self, *args, **kwargs):
        self.user_setup_kwargs = kwargs.pop('setup_kwargs', {})
        self.user_code = kwargs.pop('user_code', '')
        self.script_sha = kwargs.pop('script_sha', '')
        self.init_redis(kwargs)
        self.init_dynamic_risk(kwargs)
        # 在隔离命名空间执行用户代码
        self._user_module = self._compile_user_code(self.user_code)
        super().__init__(*args, **kwargs)

    def generate_trade_decision(self, execute_result=None):
        # 1. 构造 ctx + 当日 bar
        # 2. 先调 on_universe（如有）
        # 3. 遍历 universe 调 on_bar
        # 4. 收集订单，转成 TradeDecisionWO
        ...
```

### 10.3 翻译触发流程

```
用户在 Strategy Lab 点 [📤 转模板]
   ↓
前端 → POST /strategy-lab/translate-to-template
   ↓
后端：
  1. 跑 4 关卡过拟合检测
  2. 评分 < 70 拒绝（"请先解决警告"）
  3. AST 解析 → 生成 .json + .py
  4. 写入 strategy_templates/ 目录
  5. invalidate templates cache
   ↓
返回模板 ID + 跳转链接（去策略向导预览）
```

---

## 11. 每日扫描 Cron

### 11.1 定时任务

```python
# backend/services/engine/strategy_lab/cron/daily_scan.py
@celery_app.task(name='strategy_lab.daily_scan')
def run_daily_scan():
    """每日 16:30（A股收盘后）扫描所有 daily_scan_enabled=true 的脚本。"""
    scripts = db.query(LabScript).filter_by(daily_scan_enabled=True).all()
    today = pd.Timestamp.now(tz='Asia/Shanghai').normalize()
    for script in scripts:
        try:
            signals = run_one_day(script.code, script.params, date=today)
            for sig in signals:
                db.add(LabSignal(
                    script_id=script.script_id,
                    user_id=script.user_id,
                    scan_date=today.date(),
                    symbol=sig.symbol,
                    direction=sig.direction,
                    reason=sig.reason,
                    detail=sig.detail,
                ))
            db.commit()
        except Exception as e:
            logger.error(f'daily_scan failed for {script.script_id}: {e}')
```

### 11.2 Dashboard 展示

`/dashboard` 加一个新卡片"今日策略信号"：

```
📊 今日策略信号 (2026-06-12)
─────────────────────────────────
[v3 斐波那契] 触发 3 只
  ▲ 600519  S2_hit   close=1810
  ▲ 002415  S1_hit   close=21.5
  ▼ 300750  R2_hit   close=235

[双均线策略] 触发 1 只
  ▲ 600036  20日金叉60日   close=42.5

[全部 12 个监控策略 →]
```

---

## 12. Sprint 计划（19 天）

### Sprint 1 (Day 1-5) — 框架搭建 + SDK 跑通

| Day | 内容 | 验收 |
|---|---|---|
| 1 | 后端 SDK Context/Bar/Position 类 + AST 安全检查 | 单元测试覆盖 90%+ |
| 2 | runner 子进程 + Redis 结果存储 + 进度 SSE | 一段最简代码能跑通返回 metrics |
| 3 | 前端三栏布局 + Monaco（复用）+ 运行按钮 | 浏览器看到 IDE，能粘代码 |
| 4 | 净值曲线 + KPI 卡 + 交易明细表（复用 EnhancedQuickBacktest 抽出组件） | 看到曲线 |
| 5 | 联调"v3 斐波那契"端到端 + AI prompt 30 题压测 | 通过率 ≥ 60% 否则改提示词 |

**里程碑**：你写 Python，能在浏览器看到净值 + 交易表

### Sprint 2 (Day 6-10) — K 线 + AI 助手 + Why 解释器

| Day | 内容 | 验收 |
|---|---|---|
| 6 | K 线 markers（复用 KlineChart.tsx）+ overlays | K线上看到 ▲▼ |
| 7 | 持仓表 + 月度热力 + 年度统计 | 全部 Tab 渲染 |
| 8 | AI 助手抽屉 + 透传 ai_ide/chat | 流式聊天 |
| 9 | 实时 diff 接受/拒绝 + 错误友好化 | 改一行代码用绿色显示 |
| 10 | Why 解释器 + 评分卡 | 点 ▲ 弹窗显示触发原因 |

**里程碑**：跟 AI 说"加 RSI"，自动改代码 → 跑 → 看 K 线买卖点

### Sprint 3 (Day 11-13) — 过拟合检测 + 参数扫描

| Day | 内容 | 验收 |
|---|---|---|
| 11 | 关卡 1+2：训测分割 + 走查 | 出报告 |
| 12 | 关卡 3+4：参数敏感度 + 蒙特卡洛 + 评分卡 | 出红字警告 |
| 13 | 数据缺失提示 + 后台下载触发 | 写 us_sp500 弹下载 |

**里程碑**：策略带 4 关卡报告，过拟合一目了然

### Sprint 4 (Day 14-16) — 闭环：翻译器 + 每日扫描

| Day | 内容 | 验收 |
|---|---|---|
| 14 | RedisFreeFormStrategy 类 + 注册 | 模板可在策略向导跑 |
| 15 | SDK→Qlib 翻译器 + 一键转模板 UI | 转模板 → 策略向导可见 |
| 16 | 每日扫描 Cron + Dashboard 信号卡 | Cron 跑通,卡片可见 |

**里程碑**：策略闭环——研究→保存→每日产信号→转模板上线

### Sprint 5 (Day 17-18) — 亮点

| Day | 内容 | 验收 |
|---|---|---|
| 17 | 手画线 → 代码可读 | 拖一条线 ctx.drawn_line() 拿到 |
| 18 | vs 上一版 + 30 个示例 Gallery | 双栏对比可看 |

### Sprint 6 (Day 19) — 联调 + 文档

| Day | 内容 | 验收 |
|---|---|---|
| 19 | AI 通过率复测 + 全链路 e2e + 用户文档 | 30 题通过率 ≥ 60%、文档入库 |

**最终里程碑**：完整产品交付。

---

## 13. 验收指标

### 13.1 功能验收（全过才算交付）

- [ ] 30 道 AI 提示词通过率 ≥ 60%
- [ ] v3 斐波那契 SDK 实现，OOS 结果与终端跑出来误差 < 1%
- [ ] 1000 万行 csi300 5 年回测在 60s 内出结果
- [ ] 4 关卡报告完整生成
- [ ] 转模板成功，模板能在策略向导跑
- [ ] 每日扫描 Cron 在测试日成功产出信号
- [ ] 沙盒：用户写 `os.system("ls")` 拒绝执行
- [ ] 沙盒：死循环代码 60s 内被杀
- [ ] 可重复性：同 script_sha + data_snapshot_at 重跑结果差 < 1e-6

### 13.2 性能验收

| 指标 | 目标 |
|---|---|
| 同步回测（csi300，1 年） | < 30s |
| 异步回测（csi300，5 年） | < 5 min |
| K 线渲染（1 年日 K） | < 500 ms |
| 编辑器 hover 提示响应 | < 100 ms |
| AI 流式响应首 token | < 2s |

### 13.3 易用性验收

- [ ] 新用户 5 分钟内能跑完一个完整策略（无人工指导）
- [ ] 错误信息均带"修改建议"
- [ ] 数据缺失自动提示，用户不需要看日志

---

## 14. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| AI 通过率 < 60% | 中 | 高（招牌立不住） | Sprint 1 末跨集 → 不过迭代提示词 |
| RedisFreeFormStrategy 与 Qlib 不兼容 | 中 | 高（断头） | Sprint 4 早做 POC、降级为"研究态"模板 |
| 沙盒被钻空 | 低 | 高（事故） | 三层防护、AST + subprocess + 容器 |
| 性能不达标 | 中 | 中 | 关键路径 cython/numba 优化预留口子 |
| 用户冷启动 | 高 | 中 | 30 个示例 + Gallery + 文档 |
| 与平台模板冲突（命名/字段） | 低 | 中 | 翻译时强制 `lab_` 前缀 |

---

## 15. 附录

### 15.1 30 个内置示例（Gallery）

| # | 名称 | 类型 | 难度 |
|---|---|---|---|
| 1 | 双均线（20×60） | 单股趋势 | 入门 |
| 2 | MACD 金叉死叉 | 单股趋势 | 入门 |
| 3 | RSI 超卖反弹 | 单股震荡 | 入门 |
| 4 | 布林带突破 | 单股震荡 | 入门 |
| 5 | KDJ 金叉 | 单股震荡 | 入门 |
| 6 | 动量 Top10 | 横截面 | 入门 |
| 7 | 价值股（PE+ROE） | 横截面 | 入门 |
| 8 | PEG < 1 选股 | 横截面 | 中级 |
| 9 | 五行选股（金木水火土） | 横截面玄学 | 入门 |
| 10 | A/B 斐波那契 v3 | 单股几何 | 中级 |
| 11 | A/B 斐波那契走查 v4 | 训练+OOS | 中级 |
| 12 | 海龟交易（20/55日突破） | 单股趋势 | 中级 |
| 13 | 双均线 + 量能确认 | 单股+辅助 | 中级 |
| 14 | 行业轮动（动量行业 Top3） | 行业 | 中级 |
| 15 | 小市值反转 | 横截面 | 中级 |
| 16 | 破净（PB<1） + ROE 转正 | 横截面 | 中级 |
| 17 | 北上资金跟随 | 横截面 | 高级 |
| 18 | 连板打板 | 单股事件 | 高级 |
| 19 | 财报前埋伏 | 事件 | 高级 |
| 20 | 龙虎榜跟随 | 事件 | 高级 |
| 21 | 隔夜跳空策略 | 单股 | 高级 |
| 22 | 50 ETF 套利 | 跨品种 | 高级 |
| 23 | 配对交易 | 双股 | 高级 |
| 24 | 因子合成（3 因子等权） | 横截面 | 高级 |
| 25 | 风险平价 | 组合 | 高级 |
| 26 | 趋势跟踪 + 动态止损 | 单股 | 高级 |
| 27 | 网格交易 | 单股 | 中级 |
| 28 | 港股恒生科技选股 | 跨市场 | 中级 |
| 29 | 美股 SPY 反转 | 跨市场 | 中级 |
| 30 | 多因子打分 + Top30 | 横截面 | 高级 |

### 15.2 SDK API 速查表

详见 §4.3，此处略。

### 15.3 文件清单（开发时新增/修改）

#### 后端新增
```
backend/services/engine/strategy_lab/  (整个目录)
backend/services/engine/qlib_app/utils/extended_strategies.py  (+RedisFreeFormStrategy)
backend/migrations/xxxx_add_strategy_lab_tables.py
strategy_templates/lab_*.json/.py  (翻译器产物)
docs/Strategy_Lab规范.md  (本文档)
```

#### 前端新增
```
electron/src/features/strategy-lab/  (整个目录)
electron/src/App.tsx  (+/strategy-lab 路由)
```

#### 复用抽取
```
electron/src/components/Editor/CodeEditor.tsx  (从 AIIDEPage 抽出)
electron/src/components/AIChatPanel/  (从 AIIDEPage 抽出)
electron/src/components/BacktestResult/EquityCurve.tsx (从 EnhancedQuickBacktest 抽出)
electron/src/components/BacktestResult/KpiCards.tsx (同上)
```

### 15.4 名词索引

| 词 | 含义 |
|---|---|
| SDK | Strategy Lab 自创策略写法 (`setup` + `on_bar` + `on_universe`) |
| Context (`ctx`) | SDK 暴露的全局对象 |
| Bar | 一根 K 线（OHLCV + 因子） |
| Universe | 股票池 |
| 横截面 | 同一天对比多股选股 |
| 时序 | 同一只股票按时间触发 |
| 走查回测 (Walk-Forward) | 滚动训练/测试 |
| Why 解释器 | 点交易点显示触发原因 |
| 4 关卡 | 过拟合检测的四个步骤 |
| 翻译器 | SDK → Qlib RedisFreeFormStrategy |

---

## 16. 决议记录

| 日期 | 决策 | 决策人 |
|---|---|---|
| 2026-06-12 | SDK 风格：自创事件驱动（非裸 Qlib） | 用户 |
| 2026-06-12 | 沙盒方案：subprocess + AST | 用户 |
| 2026-06-12 | 脚本可见性：私人（默认） | 用户 |
| 2026-06-12 | 范围：全量 v1（包含闭环 + 4 关卡 + 每日扫描） | 用户 |
| 2026-06-12 | 工作量：19 天 | 用户 |
| 2026-06-12 | AI 通过率：硬卡 60% | 用户 |

---

**文档结束。下一步：进入 Sprint 1 Day 1 开始实现。**
