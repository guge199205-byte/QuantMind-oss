# components

用途：可复用的 UI 组件。

## 说明
- 归属路径：electron\src\features\strategy-comparison\components
- 修改本目录代码后请同步更新本 README

- 指标比较口径修复（2026-04-08）：
  - `max_drawdown` / `drawdown` 按绝对值比较，越接近 0 越优；
  - 这适用于表格最佳值标记和回测对比页的优劣判定。
