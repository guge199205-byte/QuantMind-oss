# stock_daily_latest 数据表维护与技术白皮书

> **文档版本**：v2026.05.09  
> **更新摘要**：label → 自动分类 (0-3)；inst_ownership → 流通比例；lrg_trd → 大单层级 B_Num_L/S_Num_L；全字段 89/89 可用。

---

## 一、 数据表定位
`stock_daily_latest` 是 QuantMind 投研平台与回测引擎的核心"事实表"。它集成了行情、财务、技术指标与机器学习因子，为前端 UI 展示和后端 AI 策略生成提供统一口径。

**表规模**：89 个维度（列），覆盖基础行情、估值、技术指标、资金流向、行业概念、市场微结构等全量因子。

---

## 二、 全量字段字典（89维）

### 1. 基础信息 (8个)
| 字段名 | 类型 | 说明 | 单位/格式 |
| :--- | :--- | :--- | :--- |
| `trade_date` | DATE | 交易日期 | YYYY-MM-DD |
| `symbol` | TEXT | 股票代码 | Prefix (SH600036) |
| `stock_name` | TEXT | 股票简称 | 字符串 |
| `listed_days` | INT | 上市天数 | 天 |
| `is_st` | INT | 是否为ST股票 | 0=正常, 1=ST/*ST |
| `listing_market` | TEXT | 上市板块 | 主板/创业板/科创板 |
| `industry` | TEXT | 申万一级行业 | 字符串 |
| `province` | TEXT | 所属省份 | 字符串 |

### 2. 基础行情 (8个)
| 字段名 | 类型 | 说明 | 单位/格式 |
| :--- | :--- | :--- | :--- |
| `open` | FLOAT | 开盘价 | 元 (CNY) |
| `high` | FLOAT | 最高价 | 元 (CNY) |
| `low` | FLOAT | 最低价 | 元 (CNY) |
| `close` | FLOAT | 收盘价 | 元 (CNY) |
| `volume` | FLOAT | 成交量 | 股 |
| `amount` | FLOAT | 成交额 | 元 (CNY) |
| `pct_change` | FLOAT | 涨跌幅 | 比率 (0.05=5%) |
| `turnover_rate` | FLOAT | 换手率 | 百分比 (5=5%) |
| `adj_factor` | FLOAT | 复权因子 | 数值 (以数据库实际值为准) |

### 3. 估值指标 (8个)
| 字段名 | 类型 | 说明 | 单位/格式 |
| :--- | :--- | :--- | :--- |
| `pe_ttm` | FLOAT | 动态市盈率 | 倍 |
| `pb` | FLOAT | 市净率 | 倍 |
| `total_mv` | FLOAT | 总市值 | 元 (CNY) |
| `float_mv` | FLOAT | 流通市值 | 元 (CNY) |
| `bp` | FLOAT | 账面市值比 (1/PB) | 比率 |
| `ep_ttm` | FLOAT | 盈利收益率 (1/PE) | 比率 |
| `ln_mv_total` | FLOAT | 总市值的对数 | 数值 |
| `roe` | FLOAT | 净资产收益率 | 百分比 (12=12%) |

### 4. 收益率序列 (6个)
| 字段名 | 类型 | 说明 | 单位/格式 |
| :--- | :--- | :--- | :--- |
| `return_1d` | FLOAT | 当日收益率 | 比率 |
| `return_3d` | FLOAT | 近3日收益率 | 比率 |
| `return_5d` | FLOAT | 近5日收益率 | 比率 |
| `return_10d` | FLOAT | 近10日收益率 | 比率 |
| `return_20d` | FLOAT | 近20日收益率 | 比率 |
| `return_60d` | FLOAT | 近60日收益率 | 比率 |

### 5. 均线系统 (7个)
| 字段名 | 类型 | 说明 | 单位/格式 |
| :--- | :--- | :--- | :--- |
| `ma5/10/20/60` | FLOAT | 5/10/20/60日均线 | 元 (CNY) |
| `ma_gap_5` | FLOAT | 5日均线偏离度 | 比率 (Price-MA5)/MA5 |
| `ma_gap_10` | FLOAT | 10日均线偏离度 | 比率 |
| `ma_gap_20` | FLOAT | 20日均线偏离度 | 比率 |

### 6. 技术指标 (9个)
| 字段名 | 类型 | 说明 | 单位/格式 |
| :--- | :--- | :--- | :--- |
| `rsi_6` | FLOAT | RSI (6日) | 0-100 |
| `rsi_14` | FLOAT | RSI (14日) | 0-100 |
| `kdj_k/d/j` | FLOAT | KDJ 指标 | 0-100 |
| `macd_dif` | FLOAT | MACD 快线 | 数值 |
| `macd_dea` | FLOAT | MACD 慢线 | 数值 |
| `macd_hist` | FLOAT | MACD 柱状图 | 数值 |
| `beta_20` | FLOAT | 20日贝塔系数 | 数值 |

### 7. 波动与量能 (10个)
| 字段名 | 类型 | 说明 | 单位/格式 |
| :--- | :--- | :--- | :--- |
| `vol_std_5/20/60` | FLOAT | 5/20/60日波动率 | 比率 (标准差) |
| `vol_atr_14` | FLOAT | 14日平均真实振幅 | 数值 |
| `volume_ratio_5` | FLOAT | 5日量比 | 倍 |
| `volume_ratio_20` | FLOAT | 20日量比 | 倍 |
| `volume_ma_3/5` | FLOAT | 3/5日平均成交量 | 股 |
| `amount_ma_5` | FLOAT | 5日平均成交额 | 元 (CNY) |
| `volume_trend_3d` | FLOAT | 3日成交量趋势 | 比率 |

### 8. 行业概念与标签 (14个)
| 字段名 | 类型 | 说明 | 单位/格式 |
| :--- | :--- | :--- | :--- |
| `ind_code_l1/l2` | TEXT | 行业代码 | 字符串 |
| `label` | INT | 自动分类标签: 0=周期/其他, 1=价值, 2=成长, 3=价值成长 | 整数 |
| `concept_ai` | INT | 是否属于AI概念 | 0/1 |
| `concept_chip` | INT | 是否属于芯片概念 | 0/1 |
| `concept_new_energy`| INT | 是否属于新能源概念 | 0/1 |
| `concept_pv` | INT | 是否属于光伏概念 | 0/1 |
| `concept_military` | INT | 是否属于军工概念 | 0/1 |
| `concept_medical` | INT | 是否属于医药概念 | 0/1 |
| `concept_fintech` | INT | 是否属于金融科技概念| 0/1 |
| `concept_consumption`| INT | 是否属于大消费概念 | 0/1 |
| `concept_state_owned`| INT | 是否属于国资委背景 | 0/1 |
| `concept_lithium` | INT | 是否属于锂电池概念 | 0/1 |

### 9. 资金持仓流向 (7个)
| 字段名 | 类型 | 说明 | 单位/格式 |
| :--- | :--- | :--- | :--- |
| `main_flow` | FLOAT | 主力资金净流入 | 元 (CNY) |
| `inst_ownership` | FLOAT | 流通市值占比 (float_mv/total_mv) | 比率 (0.3=30%) |
| `lrg_trd_tolbuynum` | FLOAT | 大单买入笔数 (B_Num_L) | 笔 |
| `lrg_trd_tolsellnum`| FLOAT | 大单卖出笔数 (S_Num_L) | 笔 |
| `flow_net_amount` | FLOAT | 资金总净流入额 | 元 (CNY) |
| `b_volume` | FLOAT | 外盘(主动买入)量 | 股 |
| `s_volume` | FLOAT | 内盘(主动卖出)量 | 股 |

### 10. 指数关联属性 (5个)
| 字段名 | 类型 | 说明 | 单位/格式 |
| :--- | :--- | :--- | :--- |
| `idx_all` | INT | 全A股集合 | 1 |
| `idx_hs300` | INT | 沪深300成分股 | 0/1 |
| `idx_zz1000` | INT | 中证1000成分股 | 0/1 |
| `idx_margin` | INT | 融资融券标的 | 0/1 |
| `idx_chinext` | INT | 创业板指成分股 | 0/1 |

### 11. 市场微结构 (3个)
| 字段名 | 类型 | 说明 | 单位/格式 |
| :--- | :--- | :--- | :--- |
| `micro_effective_spread` | FLOAT | 有效价差 | 数值 |
| `micro_imbalance_volume` | FLOAT | 指数订单不平衡量 | 数值 |
| `micro_jump_flag` | INT | 价格跳变标记 | 0/1 |

### 12. 特殊交易状态 (3个)
| 字段名 | 类型 | 说明 | 单位/格式 |
| :--- | :--- | :--- | :--- |
| `consecutive_limit_up_days` | INT | 连板天数 | 天 |
| `limit_up_today` | INT | 今日是否涨停 | 0/1 |
| `limit_down_today` | INT | 今日是否跌停 | 0/1 |

### 13. 其他核心财务 (1个)
| 字段名 | 类型 | 说明 | 单位/格式 |
| :--- | :--- | :--- | :--- |
| `profit_growth` | FLOAT | 净利润同比增长率 | 比率 (0.15=15%) |

---

## 三、 使用规范与建议
1. **策略过滤**: 在使用 `f_{field}` 前缀进行过滤时，请严格参考上表中的“单位/格式”列。
2. **数据时效**: 盘前选股优先使用 `trade_date = CURRENT_DATE - 1` 的快照。
3. **空值处理**: 部分微结构或深度财务指标可能存在空值 (NULL)，策略逻辑中应包含 `dropna` 或填充逻辑。
4. **覆盖率**: 76 字段 ≥95%，13 字段 91-93%（pe_ttm/ep_ttm 74% 因亏损股无PE），详见《数据覆盖白皮书》。
5. **数据源**: 唯一事实源为 `fundamental_aligned.parquet`，PG `stock_daily_latest` 由 `scripts/sync_parquet_to_pg.py` 同步。
