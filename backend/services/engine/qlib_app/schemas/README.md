# Qlib Schemas

数据模型定义。

## 参数优化异步响应
- `OptimizationTaskResponse` 用于异步优化提交后的任务信息返回。
- `QlibOptimizationRequest / QlibOptimizationResult / OptimizationTaskResult / OptimizationParamRange` 用于网格参数优化完整请求-结果链路。
- `QlibGeneticOptimizationRequest / QlibGeneticOptimizationResult / GeneticHistoryRecord` 用于遗传算法优化请求、代际历史与结果返回。

## 高级分析风险指标口径调整
- `BasicRiskMetrics` 移除 `information_ratio` 字段（该值在当前基础风险链路中无稳定基准可比口径，容易产生误导性 0/NaN）。
- 基础风险响应保留可稳定计算指标：`total_return / annualized_return / volatility / sharpe_ratio / max_drawdown / calmar_ratio / sortino_ratio` 等。

## 交易统计指标补充
- `TradeStatsMetrics` 新增 `profit_loss_days_ratio`（盈亏天数比，盈利交易日/亏损交易日）。
- 说明：用于替代在无真实单笔 `pnl` 时语义不稳定的“盈亏比”展示。

## 策略参数补充
- `QlibStrategyParams` 增加权重策略参数（`min_score`/`max_weight`），用于遗传算法优化。

## 健康检查模型
- `HealthCheckResponse` 统一 qlib 健康响应结构（含 qlib、DB、Redis 状态）。

## 回测动态仓位参数
- `QlibBacktestRequest` 增加动态仓位相关字段：
  - `dynamic_position`：是否启用动态仓位
  - `style`：策略风格（用于云端配置下发）
  - `market_state_symbol`：市场状态参考指数
  - `market_state_window`：滚动窗口（交易日）
  - `strategy_total_position`：策略在总资金中的占比

## 异步回测 ID 透传
- `QlibBacktestRequest` 新增 `backtest_id` 可选字段。
- 用途：异步模式下由 API 层注入，Celery Worker 透传到执行层，避免执行时生成新 ID 导致状态轮询断链。

## 历史来源标记
- `QlibBacktestRequest` 新增 `history_source` 字段：
  - `manual`：普通/快速回测（默认）
  - `optimization`：参数优化过程中产生的子回测
- 用途：支持历史接口按来源过滤，默认隐藏优化子任务，避免污染普通回测历史。
