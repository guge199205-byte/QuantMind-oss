# shared

用途：与 shared 相关的前端实现。

## 说明
- 归属路径：electron\src\shared
- 修改本目录代码后请同步更新本 README

## 更新记录

- 2026-03-29：`n_drop` 自动补全逻辑按策略类型细化。
- 对包含 `max_weight` 且未声明 `n_drop` 的权重型模板（如 `alpha_cross_section`、`full_alpha_cross_section`）不再注入 `n_drop`，避免前端误显示“每日最大调仓数”。
- 2026-03-29：统一模板默认调仓比例为 20%。
- `strategyParams` 默认值改为按 `n_drop = topk * 20%`（四舍五入，最少为 1）自动推导。
- 2026-03-29：修复 `long_short_topk` 默认参数容错。
- 当模板元数据缺失 `long_exposure`/`short_exposure` 时，前端默认回退到 `1.0/1.0`。
- 避免参数面板首次渲染出现“空头 1.00x / 多头 0.00x”。
