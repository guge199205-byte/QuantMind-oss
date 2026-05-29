# types

用途：类型定义与接口声明。

## 说明
- 归属路径：electron\src\types
- 修改本目录代码后请同步更新本 README

## 近期更新
- 新增 `liveTrading.ts`（2026-03-13）：
  - 定义 `ExecutionConfig`、`LiveTradeConfig`、`DeployMode`、`StrategyLiveDefaults`；
  - 用于实盘执行参数向导与 `realTradingService` 的接口类型收敛；
  - 将执行风控参数与调仓/买卖时间点参数分离，避免都混在单一 `execution_config` 中。
