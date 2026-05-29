用途：给模型策略生成提供 `f_` 参数化过滤规范（与回测/托管执行口径一致）。

规则：
1) 格式：`f_{field}_{op}`，其中 op 支持：
   - `_max`：<=
   - `_min`：>=
   - `_not`：!=
   - `_in`：in
   - 无后缀：==
2) 仅对静态/低频因子使用 `f_` 过滤（估值、市值、ST、行业、上市天数等）。
3) 严禁虚构字段名；字段必须来自平台统一特征口径。
4) 默认过滤建议：`f_is_st_not=1`、`f_listed_days_min>=60`。

常用字段示例：
- 估值：`pe_ttm`, `pb`, `roe`
- 市值：`total_mv`, `float_mv`
- 状态：`is_st`, `listed_days`
- 分类：`industry`, `listing_market`
- 指数：`idx_hs300`, `idx_zz1000`

推荐组合示例：
```python
"kwargs": {
    "signal": "<PRED>",
    "topk": 50,
    "n_drop": 5,
    "rebalance_days": 3,
    "only_tradable": True,
    "f_is_st_not": 1,
    "f_total_mv_min": 1e9,
    "f_total_mv_max": 5e10,
    "f_pe_ttm_max": 30,
    "f_roe_min": 0.08,
    "f_industry_in": ["医药", "电子"]
}
```

注意：
- 如果用户明确要求“盘中实时价格/涨跌幅过滤”，应放在策略逻辑中动态处理，不要误用 `f_`。
- 生成策略时优先 `RedisRecordingStrategy`，确保 `f_` 参数能被平台自动识别并执行。
