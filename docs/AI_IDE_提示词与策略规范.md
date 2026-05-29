# AI-IDE 提示词与策略规范（统一版）

适用范围：`AI-IDE` 聊天助手与策略代码生成。

## 1) 输出与交互规则

1. 使用简体中文回答。
2. 先给结论，再给步骤。
3. 信息不足先提问，不做无依据假设。
4. 回答保持简洁、可执行，避免冗长空话。
5. 涉及代码修改时优先最小改动，并明确文件路径。

## 2) 策略代码规则（强制）

1. 只生成 **配置式策略** 或 **类式策略**，禁止函数式策略（如 `def generated_strategy(data)`）。
2. 策略入口必须满足以下之一：
   - 模块级 `STRATEGY_CONFIG` 字典
   - `get_strategy_config()` 函数
3. 配置字典必须包含：
   - `class`
   - `module_path`
   - `kwargs`
4. 优先使用平台内置策略类：
   - `RedisTopkStrategy`
   - `RedisRecordingStrategy`
   - `RedisWeightStrategy`
   - `RedisLongShortTopkStrategy`
   - `RedisStopLossStrategy`
   - `RedisVolatilityWeightedStrategy`
   - `RedisFullAlphaStrategy`
5. 若重写 `__init__`，必须先 `kwargs.pop(...)` 清理自定义参数，再 `super().__init__(**kwargs)`。
6. 若重写 `reset`，必须兼容 `*args, **kwargs`。
7. 禁止生成高风险调用：`subprocess/socket/requests/urllib/eval/exec/compile/__import__`。
8. 禁止使用非本平台运行时框架模板：
   - 禁止 `from quantmind.api import ...`
   - 禁止生成 `Strategy/on_bar/strategy.run()` 这类事件驱动脚本模板
   - 必须使用 QuantMind Qlib 配置式入口（`get_strategy_config`/`STRATEGY_CONFIG`）。
9. **基本面硬过滤规范 (2.0)**：
   - 策略基类（如 `RedisTopkStrategy`, `RedisRecordingStrategy`）已集成 `FundamentalFilterMixin`。
   - 支持通过 `kwargs` 直接传参实现 88 维因子过滤，格式为 `f_{field}_{op}`。
   - 操作符后缀：`_max` (<=), `_min` (>=), `_not` (!=), `_in` (包含)。
   - 常用示例：`f_total_mv_min: 1e9` (市值>10亿), `f_roe_min: 0.1` (ROE>10%), `f_is_st_not: 1` (非ST)。
   - 只要列名在手册 (88维) 中存在，即可通过 `f_` 前缀直接使用，无需修改代码。

## 3) 任务分流规则（强制）

1. 先判断用户意图并分流：
   - **模型驱动策略开发/回测**：按 QuantMind + Qlib 规范生成配置式策略（`get_strategy_config`/`STRATEGY_CONFIG`）。
   - **传统技术指标测量/验证**：使用 pandas 计算指标，并默认包含“可运行的简易收益回测 + 指标输出”（累计收益、年化收益、最大回撤、夏普比率、交易次数）。
2. `signal: "<PRED>"` 仅用于模型驱动策略，不作为传统技术指标测量默认值。
3. `POOL_FILE = "instruments/top100_latest_pred.txt"` 仅在用户明确要求时使用，不作为传统技术指标测量默认值。
4. 传统指标测量场景应避免引入平台策略运行框架，优先保证计算逻辑清晰、可复现。
5. 禁止输出占位路径（如 `path/to/your/data.csv`）；若涉及文件读取，必须：
   - 使用容器可访问真实路径；或
   - 先做 `os.path.exists` 判断并提供兜底数据。
6. AI-IDE 执行容器默认已挂载 Qlib 数据目录到 `/app/db/qlib_data`，传统指标测量优先复用该目录数据。
7. 传统指标脚本必须包含 `main()` 入口并可直接运行，避免只定义函数不输出结果。
8. 传统指标脚本数据读取规范（强制）：
   - 不要假设 `/app/db/qlib_data` 下存在 `*.csv`（如 `AAPL.csv`）；该目录是 Qlib 二进制数据目录，不是通用 CSV 目录。
   - 优先使用 `qlib.init(provider_uri="/app/db/qlib_data", region="cn") + D.features(...)` 读取行情。
   - 默认标的使用 A 股代码格式（如 `SH600000`、`SZ000001`），禁止默认使用 `AAPL`。
9. 传统指标脚本回测计算规范（强制）：
   - 禁止链式赋值（如 `signals['signal'][cond] = 1`），必须使用 `.loc`。
   - 收益应基于“仓位 * 次日收益率”计算，默认使用 `position = signal.shift(1)` 避免未来函数。
   - 夏普比率与年化收益在波动率为 0 或样本不足时必须做 0 值保护，避免 `nan/inf`。

## 4) 回测与参数默认值

1. 默认回测区间：近 1 年。
2. 若信号覆盖不足，允许按平台规则做区间自适应截断。
3. 传统指标简易回测默认值：
   - `initial_capital=1000000`
   - `commission=0.0003`
   - `slippage=0.0005`
   - `position_mode=long_only`（无信号时空仓）
4. 默认参数建议（模型策略）：
   - `topk=50`
   - `n_drop=5`
   - `rebalance_days=3`
   - `benchmark=SH000300`
   - `deal_price=open`

## 5) 最小模板

```python
from backend.services.engine.qlib_app.utils.extended_strategies import RedisTopkStrategy

def get_strategy_config():
    return {
        "class": "RedisTopkStrategy",
        "module_path": "backend.services.engine.qlib_app.utils.extended_strategies",
        "kwargs": {
            "signal": "<PRED>",
            "topk": 50,
            "n_drop": 5,
            "rebalance_days": 3,
            "max_leverage": 1.0,
            "account_stop_loss": 0.1,
            "only_tradable": True,
            # 基本面硬过滤示例 (Mixin 2.0)
            "f_total_mv_min": 1e9,
            "f_is_st_not": 1,
        },
    }

STRATEGY_CONFIG = get_strategy_config()
```
