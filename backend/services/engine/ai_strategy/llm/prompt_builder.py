"""LLM Prompt 构建器 - 策略生成和修复的提示模板"""

from textwrap import dedent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..api.schemas.generation import GenerateRequest


def build_strategy_prompt(body: "GenerateRequest", dsl: str) -> str:
    """构建策略生成的 LLM 提示词。

    遵循 QuantMind V2 策略规范，生成配置式策略代码。
    """
    buy_desc = ", ".join([b.name for b in body.buyRules]) or "无特定买入规则"
    sell_desc = ", ".join([s.name for s in body.sellRules]) or "无特定卖出规则"
    symbols = []
    if body.context and isinstance(body.context.get("symbols"), list):
        symbols = [s for s in body.context.get("symbols", []) if s]
    symbol_context = ", ".join(symbols) if symbols else "不限"
    risk_desc = body.risk.rebalanceFrequency or "monthly"
    prompt = dedent(f"""
        你是一个专注于量化策略的 AI 工程师，正在为 QuantMind 平台生成符合 V2 规范的 Python 策略。

        === QuantMind V2 策略规范（强制遵守）===
        1. 策略入口：必须定义 STRATEGY_CONFIG 字典或 get_strategy_config() 函数，返回包含 class/module_path/kwargs 的字典。
        2. 策略基类：优先使用平台内置策略类：
           - RedisTopkStrategy (module_path: backend.services.engine.qlib_app.utils.extended_strategies)
           - RedisRecordingStrategy (module_path: backend.services.engine.qlib_app.utils.recording_strategy)
           - RedisWeightStrategy (module_path: backend.services.engine.qlib_app.utils.recording_strategy)
           - RedisLongShortTopkStrategy, RedisStopLossStrategy, RedisVolatilityWeightedStrategy, RedisFullAlphaStrategy
        3. 仅当用户明确要求“模型驱动策略/AI 预测信号策略”时，signal 使用 "<PRED>" 表示平台默认预测信号。
        3.1 若用户仅要求“传统技术指标测量/验证”（MACD/RSI/KDJ/BOLL 等），请改为 pandas 指标计算 + 简易收益回测脚本。
            必须输出：累计收益、年化收益、最大回撤、夏普比率、交易次数。
            默认参数：initial_capital=1000000, commission=0.0003, slippage=0.0005。
            数据读取必须遵循：
            - 使用 qlib.init(provider_uri="/app/db/qlib_data", region="cn") + D.features(...)；
            - 不要生成 /app/db/qlib_data/AAPL.csv 这类路径；
            - 默认标的使用 A 股代码（如 SH600000/SZ000001）。
            回测计算必须遵循：
            - 使用 .loc 赋值，禁止链式赋值；
            - 使用 position=signal.shift(1) 计算策略日收益，避免未来函数；
            - 对波动率为 0 时的夏普比率做保护（返回 0）。
        4. 自定义策略类若重写 __init__，必须先 pop 自定义参数再调用 super().__init__(**kwargs)。
        5. 安全禁用：禁止使用 os, sys, subprocess, shutil, requests, urllib, socket, eval, exec, compile。
        6. 默认参数：topk=50, n_drop=5, rebalance_days=3。
        7. 严禁生成非本平台模板（仅限模型策略场景）：
           - 禁止 `from quantmind.api import ...`
           - 禁止 Strategy/on_bar/strategy.run() 事件驱动脚本模板
           - 必须输出 get_strategy_config()/STRATEGY_CONFIG 配置式策略

        === 策略类型选择指南 ===
        1. 简单 TopK 选股：直接使用 RedisTopkStrategy，无需自定义类
        2. 需要自定义选股逻辑：继承 RedisTopkStrategy，覆写 generate_target_weight_position() 方法
        3. 需要权重分配：继承 RedisWeightStrategy，覆写 generate_target_weight_position() 方法

        === 最简合规模板（模型策略 / 简单 TopK）===
        ```python
        from backend.services.engine.qlib_app.utils.extended_strategies import RedisTopkStrategy

        def get_strategy_config():
            return {{
                'class': 'RedisTopkStrategy',
                'module_path': 'backend.services.engine.qlib_app.utils.extended_strategies',
                'kwargs': {{
                    'signal': '<PRED>',
                    'topk': 50,
                    'n_drop': 5,
                    'rebalance_days': 3,
                    'max_leverage': 1.0,
                    'account_stop_loss': 0.1,
                    'only_tradable': True,
                }}
            }}

        STRATEGY_CONFIG = get_strategy_config()
        ```

        === 自定义策略模板（模型策略 / 需要自定义选股逻辑时使用）===
        ```python
        from backend.services.engine.qlib_app.utils.extended_strategies import RedisTopkStrategy
        import pandas as pd
        import numpy as np

        class MyCustomStrategy(RedisTopkStrategy):
            def __init__(self, my_param=10, **kwargs):
                self.my_param = my_param
                super().__init__(**kwargs)

            def generate_target_weight_position(self, score, current=None, trade_exchange=None, **kwargs):
                # 在这里实现自定义选股逻辑
                # score 是预测信号，可以修改或忽略
                # 返回值必须是 {{stock_id: weight}} 字典
                return super().generate_target_weight_position(score, current, trade_exchange, **kwargs)

        def get_strategy_config():
            return {{
                'class': 'MyCustomStrategy',
                'module_path': __name__,
                'kwargs': {{
                    'signal': '<PRED>',
                    'topk': 50,
                    'n_drop': 5,
                    'my_param': 10,
                }}
            }}

        STRATEGY_CONFIG = get_strategy_config()
        ```

        === 用户需求 ===
        DSL: {dsl}
        买入规则: {buy_desc}
        卖出规则: {sell_desc}
        风控周期: {risk_desc}
        目标股票池示例: {symbol_context}

        === 输出要求 ===
        只能返回完整的 Python 代码（带必要注释），不要额外补充解释性文字。
        代码必须包含 STRATEGY_CONFIG 或 get_strategy_config() 入口。
        不要生成函数式策略（如 def generated_strategy(data)）。
        不要定义不会被调用的方法（如 _rule_based_policy），必须覆写 generate_target_weight_position()。
        若是模型策略，严禁输出 `from quantmind.api`、`on_bar`、`strategy.run()` 模板。
        """)
    return prompt.strip()


def build_repair_prompt(code: str, err: str) -> str:
    """构建代码修复的 LLM 提示词。

    从 steps/step5_generation.py._repair_prompt 提取。
    """
    return dedent(f"""
        下面是一段 Python 代码，存在语法/结构问题：{err}

        请你修复它，要求：
        1. 输出必须是完整的 Python 代码文件
        2. 保持原有功能和结构，尽量少改动
        3. 不要输出 markdown 代码块，不要解释，只输出代码

        待修复代码：
        {code}
        """).strip()
