# backtest

用途：回测相关功能。

## 说明
- 归属路径：electron\src\types\backtest
- 修改本目录代码后请同步更新本 README

## 近期更新
- QlibStrategyParams 增加 `min_score`/`max_weight`，用于 WeightedStrategy 遗传优化。
- `StrategyFile` 新增可选字段（2026-03-13）：
  - `execution_config`
  - `live_trade_config`
  - `execution_defaults`
  - `live_defaults`
  - `live_config_tips`
  用于在实盘交易页面为默认/用户策略回填推荐的实盘执行参数。
