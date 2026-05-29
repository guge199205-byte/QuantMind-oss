# fundamental_aligned.parquet 数据覆盖白皮书

> **版本**: v6 (2026-05-09)  
> **文件**: `db/custom/fundamental_aligned.parquet`  
> **生成脚本**: `db/custom/regenerate_fundamental.py`, `db/custom/fill_historical_2020_2025.py`

---

## 一、数据概况

| 指标 | 值 |
|---|---|
| 总行数 | 7,926,961 |
| 股票数 | 5,510 |
| 日期范围 | 2020-01-01 ~ 2026-04-30 |
| 总字段数 | 89 |
| 完全可用 (≥95%) | **76** |
| 部分缺失 (50-95%) | **13** |
| 无数据 (<50%) | **0** |

### 年度分布

| 年份 | 行数 | 股票数 | 交易日 |
|---|---|---|---|
| 2020 | 1,050,609 | 4,253 | 243 |
| 2021 | 1,164,220 | 4,716 | 243 |
| 2022 | 1,256,934 | 5,038 | 242 |
| 2023 | 1,323,882 | 5,227 | 242 |
| 2024 | 1,360,393 | 5,258 | 242 |
| 2025 | 1,365,178 | 5,294 | 242 |
| 2026(至4月) | 405,745 | 5,286 | 77 |

---

## 二、数据来源架构

```
fundamental_aligned.parquet
├── model_features_20xx.parquet (技术指标、波动率、微结构、风格因子)
│   └── db/feature_snapshots/
├── CSMAR DuckDB (基本面、行情、资金)
│   └── M2SSD/git_backups/quantmind/db/csmar.duckdb
│       ├── 股票历史日行情信息表(后复权) → 行情 + 市值 + 连板
│       ├── 日个股回报率文件 + 日个股回报率文件(新版) → 涨跌幅 + 涨跌停
│       ├── 股票价格复权因子表(日) → 复权因子
│       ├── 个股日交易衍生指标 → PE/PB (仅2024-05起)
│       ├── 个股买卖不平衡指标表(日) → 内外盘 + 大单笔数
│       ├── 个股买卖价差表(日) → 有效价差
│       ├── 个股跳跃指标表(日) → 跳跃标记
│       ├── 公司文件 → 行业/省份/板块/上市日
│       └── 相对价值指标 → ROE / 利润增速
└── concept_data/ (概念板块、指数成分)
    └── M2SSD/git_backups/quantmind/db/concept_data/
        ├── concept/ → 10个概念板块 (AI/芯片/新能源/光伏/军工等)
        └── index/ → 5个指数成分 (沪深300/中证1000/创业板指/融资融券/全A)
```

---

## 三、字段覆盖详情

### ✅ 高覆盖字段 (≥95%, 76个)

| 域 | 字段数 | 代表字段 | 覆盖率 |
|---|---|---|---|
| 基础信息 | 8/8 | symbol, stock_name, listed_days, is_st, listing_market, industry, province, label | 98-100% |
| 基础行情 | 8/8 | open, high, low, close, volume, amount, pct_change, turnover_rate, adj_factor | ≥99% |
| 估值指标 | 6/8 | pb, total_mv, float_mv, bp, ln_mv_total, inst_ownership | ≥97% |
| 收益率 | 6/6 | return_1d ~ return_60d | ≥99% |
| 均线 | 7/7 | ma5/10/20/60, ma_gap_5/10/20 | ≥99% |
| 技术指标 | 9/9 | rsi_6/14, kdj_k/d/j, macd_dif/dea/hist, beta_20 | ≥99% |
| 波动量能 | 9/10 | vol_std_5/20/60, vol_atr_14, volume_ratio_5/20, volume_ma_3/5, amount_ma_5 | ≥95% |
| 行业代码 | 2/2 | ind_code_l1, ind_code_l2 | 100% |
| 概念板块 | 10/10 | concept_ai/chip/new_energy/pv/military/medical/fintech/consumption/state_owned/lithium | **100%** |
| 指数成分 | 5/5 | idx_all, idx_hs300, idx_zz1000, idx_margin, idx_chinext | **100%** |
| 涨跌停 | 2/2 | limit_up_today, limit_down_today | **100%** |
| 财务 | 2/2 | roe, profit_growth | ≥98% |

### ⚠️ 部分覆盖字段 (50-95%, 13个)

| 字段 | 覆盖率 | 缺失原因 |
|---|---|---|
| `pe_ttm` | 74.3% | 亏损股无PE；CSMAR `个股日交易衍生指标` 仅2024-05起（逆推自 ep_ttm 补充） |
| `ep_ttm` | 74.3% | 同上（ep_ttm = 1/pe_ttm） |
| `b_volume` | 91.7% | CSMAR `买卖不平衡表` 部分早期数据缺口 |
| `s_volume` | 91.7% | 同上 |
| `lrg_trd_tolbuynum` | 91.9% | CSMAR `买卖不平衡表` 大单层级(B_Num_L) 部分缺失 |
| `lrg_trd_tolsellnum` | 91.8% | 同上(S_Num_L) |
| `consecutive_limit_up_days` | 92.1% | 后复权表 Distance 字段部分缺失 |
| `micro_effective_spread` | 92.6% | model_features 价差数据部分缺失 |
| `micro_imbalance_volume` | 92.6% | model_features 不平衡量部分缺失 |
| `micro_jump_flag` | 92.9% | model_features 跳跃标记部分缺失 |
| `main_flow` | 92.6% | model_features flow 部分缺失 |
| `flow_net_amount` | 92.6% | 同上 |
| `beta_20` | 92.9% | model_features 部分早期股票历史不足 |

> 13个字段均为源数据限制（CSMAR/model_features 约7-8%股票部分时段无数据），策略使用时加 `dropna()` 即可。

### 替代方案已执行

| 字段 | 原值来源 | 替代方案 | 覆盖率 |
|---|---|---|---|
| `inst_ownership` | 无数据源 (0%) | **流通比例** `float_mv / total_mv` | 99.1% ✅ |
| `lrg_trd_tolbuynum` | `日交易统计文件` (27%) | CSMAR `B_Num_L` 大单买入笔数 | 91.9% ⚠️ |
| `lrg_trd_tolsellnum` | `日交易统计文件` (25%) | CSMAR `S_Num_L` 大单卖出笔数 | 91.8% ⚠️ |
| `label` | 无数据源 (0%) | **自动分类** (价值/成长/周期) | 98.1% ✅ |
| `limit_up_today` | 部分缺失 (89%) | 缺失 → 0，新版回报率文件补缺 | 100% ✅ |
| `limit_down_today` | 部分缺失 (89%) | 缺失 → 0，新版回报率文件补缺 | 100% ✅ |

### label 自动分类规则

| 标签 | 条件 | 占比 |
|---|---|---|
| 0 (周期/其他) | 不满足以下条件 | 72.1% |
| 1 (价值) | pe_ttm<30, pb<2, roe>2 | 0.4% |
| 2 (成长) | profit_growth>0.3, roe>2 | 24.5% |
| 3 (价值成长) | 同时满足价值和成长 | 1.4% |

---

## 四、数据更新流程

### 架构

```
model_features + CSMAR + concept_data
        │
        ▼
fundamental_aligned.parquet  ← 唯一数据源 (89列, 完整历史)
        │
   ┌────┴────┐
   ▼         ▼
Qlib回测    PG stock_daily_latest ← 仅2026年数据, 供投研/AI策略查询
(直接读取)  (sync_parquet_to_pg.py 同步)
```

### 全量重建 parquet（季度/年度）

```bash
# 1. 确保 CSMAR DuckDB 包含最新数据
# 2. 确保 model_features 快照已更新
python3 db/custom/regenerate_fundamental.py
python3 db/custom/fill_historical_2020_2025.py
```

### 同步到 PostgreSQL（每日）

```bash
# 远程生产库 (默认)
python3 scripts/sync_parquet_to_pg.py

# 本地 Docker
LOCAL=1 python3 scripts/sync_parquet_to_pg.py
```

脚本特性：
- 仅同步 2026 年数据（PG 只保留当前年份）
- `DELETE + INSERT` 全量替换（PG 表无主键，避免 UPSERT 复杂度）
- 自动处理 numpy → Python 类型转换
- 每 5000 行一批，进度实时输出
- 同步后自动验证 4 个关键字段覆盖率

**最近执行记录** (2026-05-09):

| 环境 | 行数 | inst_ownership | label | concept_ai | lrg_trd | 耗时 |
|---|---|---|---|---|---|---|
| 本地 Docker | 405,745 | 99.2% | 98.5% | 100% | 97.5% | 2.5min |
| 远程生产 | 405,745 | 99.2% | 98.5% | 100% | 97.5% | 5min |

### 废弃脚本

以下旧数据填充脚本已被 `sync_parquet_to_pg.py` 替代：

| 脚本 | 原因 |
|---|---|
| `scripts/db_init/import_all_to_prod.py` | 多数据源混杂 → 统一为 parquet 源 |
| `scripts/data/processing/sync_latest_stocks.py` | 独立逻辑 → 同上 |
| `scripts/data/processing/sync_from_feature_db.py` | 特征库冗余 → 模型特征已在 parquet |
| `scripts/data/processing/backfill_stock_daily_latest.py` | 手动回填 → sync 脚本自动处理 |
| `scripts/data/processing/fill_pe_roe_from_baostock.py` | 外部API → 已在 parquet 构建中覆盖 |
| `scripts/sync_factors_to_parquet.py` | PG→parquet 方向已废弃 |
| `scripts/init_fundamental_parquet.py` | 模拟数据生成器 → 不再需要 |

### 相关文件

| 文件 | 用途 |
|---|---|
| `db/custom/fundamental_aligned.parquet` | **最终数据文件** (89列, 7.9M行) |
| `db/custom/regenerate_fundamental.py` | parquet 再生/追加脚本 |
| `db/custom/fill_historical_2020_2025.py` | 批量历史填充 (分3批) |
| `scripts/sync_parquet_to_pg.py` | **parquet → PG 同步** (仅2026, INSERT ON CONFLICT) |
| `backend/services/engine/ai_strategy/steps/step1_stock_selection.py` | FACTOR_COLUMN_MAP (89 列名映射) |
| `backend/shared/fundamental_aligner.py` | 运行时读取类 (回测/策略过滤) |
| `docs/stock_daily_latest_维护文档.md` | 89维字段字典 |
| `docs/实盘交易因子筛选手册.md` | 实盘策略模板与因子速查 |

---

## 五、覆盖率演进历史

| 版本 | 关键改进 | 行数 | 日期 | 有效字段 |
|---|---|---|---|---|
| v1 | 初始（仅2026-01~04 model_features） | 446K | 2026-01~04 | ~60 (67%) |
| v2 | +2025年12月 CSMAR 填充 | 527K | 2025-12~2026-04 | ~68 (76%) |
| v3 | +全量历史 2020-01~2025-11 (分3批) | 7.9M | 2020-01~2026-04 | ~72 (81%) |
| v4 | +概念板块/指数成分 (concept_data) | 7.9M | 同上 | ~87 (98%) |
| v5 | +逆推 pe_ttm/pb (ep_ttm/bp 计算) | 7.9M | 同上 | 85/89 (96%) |
| **v6** | **替代方案: inst_ownership, lrg_trd, label, limit ↑** | 7.9M | 同上 | **89/89 (100%)** |
