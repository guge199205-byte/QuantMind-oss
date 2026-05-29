# types

用途：类型定义与接口声明。

## 说明
- 归属路径：electron\src\shared\types
- 修改本目录代码后请同步更新本 README

- 策略对比指标口径修复（2026-04-08）：
  - `isBestValue` 对 `max_drawdown` / `drawdown` 改为按绝对值比较；
  - 避免负数回撤直接按数值大小比较导致“更负反而更优”的错误。
