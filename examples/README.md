# QuantMind 策略示例库 (Examples)

本目录提供了在 QuantMind 平台上编写、运行和调试策略的参考代码。

## 目录结构

### 1. [Qlib 核心示例](./qlib/)
展示了如何利用 Qlib 引擎进行高阶量化投研：
- `qlib_backtest_chart_demo.py`: 回测结果的可视化渲染示例。
- `qlib_complex_strategy_demo.py`: 复杂多因子组合逻辑。
- `qlib_topk_dropout_example.py`: 经典的 TopK 选股与 Dropout 换手控制。

### 2. [第三方适配器](./adapters/)
展示了如何从其他平台迁移策略：
- `jq_multi_factor_demo.py`: 聚宽 (JoinQuant) 风格的多因子适配。
- `reference_jq_strategy.py`: 存量策略迁移模板。

### 3. [测试用例](./testing/)
包含用于功能验证的最小化策略单元。

## 如何运行
确保您已激活根目录虚拟环境，并根据脚本说明执行：
\`bash
python examples/qlib/xxx_demo.py
\`
