"""
Qlib策略代码生成器
基于LLM生成符合Qlib框架规范的策略代码
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class QlibStrategyConfig(BaseModel):
    """Qlib策略配置"""

    strategy_name: str
    strategy_description: str
    strategy_type: str  # topk_dropout, weight_based, custom

    # 策略参数
    parameters: dict[str, Any]

    # 交易逻辑
    entry_logic: dict[str, Any]
    exit_logic: dict[str, Any]

    # 风控参数
    risk_degree: float = 0.95
    max_position_per_stock: float = 0.1

    # 生成信息
    llm_model: str
    user_input: str


class QlibStrategyCodeGenerator:
    """Qlib策略代码生成器"""

    def __init__(self, llm_client):
        """
        初始化生成器

        Args:
            llm_client: LLM客户端（支持Gemini/OpenAI/DeepSeek等）
        """
        self.llm_client = llm_client
        self.templates = QlibStrategyTemplates()

    async def generate_strategy(self, user_input: str, strategy_type: str = "auto") -> dict[str, Any]:
        """
        生成Qlib策略代码

        Args:
            user_input: 用户自然语言需求
            strategy_type: 策略类型（auto/topk_dropout/weight_based/custom）

        Returns:
            {
                "code": "策略Python代码",
                "config": "策略配置",
                "documentation": "策略文档",
                "validation": "验证结果"
            }
        """

        # 1. 解析需求
        requirement = await self._parse_requirement(user_input, strategy_type)

        # 2. 设计策略逻辑
        design = await self._design_strategy(requirement)

        # 3. 生成代码
        code = self._generate_code(design, requirement)

        # 4. 生成配置
        config = self._generate_config(design, requirement)

        # 5. 生成文档
        documentation = self._generate_documentation(design, requirement)

        # 6. 验证代码
        validation = self._validate_code(code)

        return {
            "code": code,
            "config": config,
            "documentation": documentation,
            "validation": validation,
            "metadata": {
                "strategy_name": design.get("strategy_name"),
                "strategy_type": requirement.get("strategy_type"),
                "generated_at": datetime.now().isoformat(),
                "llm_model": getattr(self.llm_client, "model_name", "unknown"),
            },
        }

    async def convert_strategy(
        self,
        source_code: str,
        source_platform: str,
        user_requirements: str | None = None,
    ) -> dict[str, Any]:
        """将第三方平台策略转换为Qlib格式"""
        prompt = f"""
你是一个量化策略转换专家。请将以下来自 {source_platform} 平台的 Python 策略代码转换为 Microsoft Qlib 框架格式。

**源代码:**
```python
{source_code}
```

**用户额外要求:**
{user_requirements or "无"}

**转换目标:**
1. 目标框架: Microsoft Qlib (使用 TopkDropoutStrategy 或 BaseSignalStrategy)
2. 提取原策略的核心信号计算逻辑，并将其转化为 Qlib 的信号表达式 (表达式语法需符合 Qlib 数据接口)
3. 保留原策略的风险控制逻辑 (止损、止盈、仓位限制)
4. 生成完整的、可执行的 Qlib 策略类代码

**输出格式要求:**
请以 JSON 格式返回（只返回 JSON），包含以下字段：
{{
    "success": true,
    "converted_code": "完整的 Qlib Python 代码",
    "conversion_notes": ["转换要点1", "转换要点2"],
    "warnings": ["警告1：某某逻辑在Qlib中实现有差异"],
    "suggestions": ["建议1：建议调整某某参数以适配Qlib执行器"],
    "estimated_compatibility": 85,
    "platform_differences": [
        {{
            "category": "API差异",
            "source_feature": "原平台特性描述",
            "target_equivalent": "Qlib对应实现描述",
            "notes": "详细说明",
            "manual_review_required": true
        }}
    ]
}}
"""

        response = await self.llm_client.chat(
            messages=[
                {"role": "system", "content": "你是Qlib量化专家，擅长多平台策略重构。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        # 提取并解析 JSON
        content = response.content if hasattr(response, "content") else str(response)
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = json.loads(content)

        return result

    async def _parse_requirement(self, user_input: str, strategy_type: str) -> dict[str, Any]:
        """解析用户需求"""

        prompt = f"""
你是Qlib量化策略专家。分析以下需求，提取策略关键信息。

用户需求: {user_input}

请分析并返回JSON格式（只返回JSON，不要其他文字）:
{{
    "strategy_type": "策略类型：topk_dropout（Top K选股换仓）/ weight_based（权重分配）/ custom（自定义逻辑）",
    "strategy_name": "策略名称（英文，如DoubleMAStrategy）",
    "strategy_description": "策略简短描述",

    "indicators": ["需要的技术指标，如MA5、MA20、MACD等"],
    "timeframe": "时间周期：daily/weekly/monthly",
    "universe": "股票池：csi300/csi500/all",

    "entry_conditions": [
        "入场条件描述1",
        "入场条件描述2"
    ],
    "exit_conditions": [
        "出场条件描述1",
        "出场条件描述2"
    ],

    "parameters": {{
        "topk": {{
            "value": 30,
            "description": "持仓股票数量",
            "range": [10, 100]
        }},
        "n_drop": {{
            "value": 5,
            "description": "每次换仓数量",
            "range": [1, 20]
        }}
    }},

    "risk_management": {{
        "risk_degree": 0.95,
        "max_position_per_stock": 0.1,
        "stop_loss": 0.05,
        "take_profit": 0.15
    }}
}}

注意:
1. 如果是简单的TopK选股策略，使用topk_dropout类型
2. 如果需要精确控制每只股票权重，使用weight_based类型
3. 如果有复杂的自定义逻辑，使用custom类型
4. strategy_name必须是有效的Python类名
"""

        response = await self.llm_client.chat(
            messages=[
                {
                    "role": "system",
                    "content": "你是Qlib量化策略专家，专门设计符合Qlib框架的策略。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        # 提取JSON
        content = response.content if hasattr(response, "content") else str(response)
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            requirement = json.loads(json_match.group())
        else:
            requirement = json.loads(content)

        # 自动判断策略类型
        if strategy_type == "auto":
            requirement["strategy_type"] = self._auto_detect_strategy_type(requirement)
        else:
            requirement["strategy_type"] = strategy_type

        requirement["llm_model"] = getattr(self.llm_client, "model_name", "unknown")

        return requirement

    def _auto_detect_strategy_type(self, requirement: dict[str, Any]) -> str:
        """自动检测策略类型"""

        # 如果有明确的TopK参数，使用topk_dropout
        params = requirement.get("parameters", {})
        if "topk" in params or "n_drop" in params:
            return "topk_dropout"

        # 如果提到权重、配置、仓位分配，使用weight_based
        desc = requirement.get("strategy_description", "").lower()
        if any(keyword in desc for keyword in ["权重", "weight", "配置", "allocation"]):
            return "weight_based"

        # 默认使用topk_dropout（最常用）
        return "topk_dropout"

    async def _design_strategy(self, requirement: dict[str, Any]) -> dict[str, Any]:
        """设计策略逻辑"""

        strategy_type = requirement["strategy_type"]

        prompt = f"""
基于以下需求，设计Qlib策略的详细实现逻辑。

策略类型: {strategy_type}
策略名称: {requirement.get("strategy_name")}
策略描述: {requirement.get("strategy_description")}

需求详情:
{json.dumps(requirement, indent=2, ensure_ascii=False)}

请设计策略并返回JSON格式（只返回JSON）:
{{
    "strategy_name": "{requirement.get("strategy_name")}",
    "base_class": "策略基类（TopkDropoutStrategy/BaseSignalStrategy/WeightStrategyBase）",

    "signal_calculation": {{
        "method": "信号计算方法描述",
        "indicators_used": ["使用的指标"],
        "formula": "信号计算公式或逻辑"
    }},

    "position_management": {{
        "method": "仓位管理方法",
        "sizing_logic": "仓位计算逻辑",
        "max_position": 0.1
    }},

    "trade_logic": {{
        "buy_condition": "买入条件的详细逻辑",
        "sell_condition": "卖出条件的详细逻辑",
        "rebalance_frequency": "换仓频率"
    }},

    "risk_control": {{
        "stop_loss_logic": "止损逻辑",
        "position_limit": "持仓限制",
        "drawdown_control": "回撤控制"
    }},

    "implementation_details": [
        "实现要点1",
        "实现要点2"
    ]
}}

设计要求:
1. 必须符合Qlib框架规范
2. generate_trade_decision()方法是核心
3. 考虑交易成本和滑点
4. 包含完整的风险控制
"""

        response = await self.llm_client.chat(
            messages=[
                {"role": "system", "content": "你是Qlib策略架构设计专家。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        # 提取JSON
        content = response.content if hasattr(response, "content") else str(response)
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            design = json.loads(json_match.group())
        else:
            design = json.loads(content)

        return design

    def _generate_code(self, design: dict[str, Any], requirement: dict[str, Any]) -> str:
        """生成策略代码 (包含动态仓位逻辑)"""

        strategy_type = requirement["strategy_type"]

        # 检查是否启用了动态仓位
        is_dynamic = requirement.get("risk_management", {}).get("enable_dynamic_position", False)

        # 如果启用，在 Prompt 中增加指令，或者在代码拼接时注入
        if is_dynamic:
            design["dynamic_sizing_logic"] = (
                "接入系统提供的市场热度算子，根据 (近5日均量/近120日均量) 动态调整总目标仓位乘数。"
            )

        if strategy_type == "topk_dropout":
            return self.templates.generate_topk_strategy(design, requirement, is_dynamic=is_dynamic)
        elif strategy_type == "weight_based":
            return self.templates.generate_weight_strategy(design, requirement, is_dynamic=is_dynamic)
        else:  # custom
            return self.templates.generate_custom_strategy(design, requirement, is_dynamic=is_dynamic)

    def _generate_config(self, design: dict[str, Any], requirement: dict[str, Any]) -> dict[str, Any]:
        """生成Qlib配置"""

        strategy_name = requirement.get("strategy_name", "CustomStrategy")
        parameters = requirement.get("parameters", {})

        # 提取参数默认值
        param_defaults = {}
        for param_name, param_info in parameters.items():
            if isinstance(param_info, dict):
                param_defaults[param_name] = param_info.get("value")
            else:
                param_defaults[param_name] = param_info

        config = {
            "class": strategy_name,
            "module_path": "generated_strategies",  # 自定义模块路径
            "kwargs": {
                "signal": "<signal_placeholder>",  # 需要在运行时替换
                **param_defaults,
            },
        }

        return config

    def _generate_documentation(self, design: dict[str, Any], requirement: dict[str, Any]) -> str:
        """生成策略文档"""

        doc = f"""# {requirement.get("strategy_name")} 策略文档

## 策略概述

**策略类型**: {requirement.get("strategy_type")}
**策略描述**: {requirement.get("strategy_description")}

## 策略逻辑

### 信号计算
{design.get("signal_calculation", {}).get("method", "N/A")}

使用指标: {", ".join(design.get("signal_calculation", {}).get("indicators_used", []))}

### 交易逻辑

**买入条件**:
{design.get("trade_logic", {}).get("buy_condition", "N/A")}

**卖出条件**:
{design.get("trade_logic", {}).get("sell_condition", "N/A")}

**换仓频率**: {design.get("trade_logic", {}).get("rebalance_frequency", "N/A")}

## 策略参数

"""

        parameters = requirement.get("parameters", {})
        for param_name, param_info in parameters.items():
            if isinstance(param_info, dict):
                doc += f"- **{param_name}**: {param_info.get('description', 'N/A')}\n"
                doc += f"  - 默认值: {param_info.get('value')}\n"
                doc += f"  - 范围: {param_info.get('range', 'N/A')}\n\n"

        doc += f"""
## 风险控制

{json.dumps(requirement.get("risk_management", {}), indent=2, ensure_ascii=False)}

## 使用示例

```python
from qlib.backtest import backtest
from qlib.backtest.executor import SimulatorExecutor
from qlib.data import D
from generated_strategies import {requirement.get("strategy_name")}

# 创建策略实例
strategy = {{
    "class": "{requirement.get("strategy_name")}",
    "module_path": "generated_strategies",
    "kwargs": {{
        "signal": <your_signal>,
        {", ".join([f'"{k}": {v.get("value") if isinstance(v, dict) else v}' for k, v in parameters.items()])}
    }}
}}

# 运行回测
portfolio_dict, indicator_dict = backtest(
    strategy=strategy,
    executor={{...}},
    start_time="2023-01-01",
    end_time="2024-12-31"
)
```

## 注意事项

{chr(10).join(["- " + note for note in design.get("implementation_details", [])])}

---

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**生成模型**: {requirement.get("llm_model", "N/A")}
"""

        return doc

    def _validate_code(self, code: str) -> dict[str, Any]:
        """验证生成的代码是否符合 QuantMind V2 规范"""

        validation = {"valid": True, "errors": [], "warnings": [], "suggestions": []}

        # 1. 语法检查
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            validation["valid"] = False
            validation["errors"].append(f"语法错误: {e}")

        # 2. V2 策略入口检查
        has_config = "STRATEGY_CONFIG" in code
        has_get_config = "get_strategy_config" in code
        if not has_config and not has_get_config:
            validation["errors"].append("缺少 V2 策略入口: STRATEGY_CONFIG 或 get_strategy_config()")
            validation["valid"] = False

        # 3. 策略基类检查（应使用 Redis* 系列而非原生 qlib 类）
        forbidden_bases = ["TopkDropoutStrategy", "WeightStrategyBase", "BaseSignalStrategy"]
        for fb in forbidden_bases:
            # 检查是否从 qlib 原生模块继承（而非从 backend 内部模块继承）
            if f"from qlib.contrib.strategy.signal_strategy import {fb}" in code:
                validation["warnings"].append(
                    f"使用了原生 qlib 基类 {fb}，建议替换为 Redis* 系列策略类"
                )

        # 4. 安全性检查
        dangerous_keywords = ["eval", "exec", "compile", "__import__", "os.system", "os.path"]
        for keyword in dangerous_keywords:
            if keyword in code:
                validation["errors"].append(f"发现危险操作: {keyword}")
                validation["valid"] = False

        # 5. signal 参数检查
        if '"<PRED>"' not in code and "'<PRED>'" not in code:
            validation["warnings"].append("signal 参数未使用 '<PRED>'，请确认信号来源")

        # 6. module_path 检查
        if "backend.services.engine.qlib_app" not in code:
            validation["warnings"].append(
                "module_path 未指向 backend.services.engine.qlib_app...，"
                "可能导致 CustomStrategyBuilder 无法自动补全"
            )

        # 7. __init__ pop 约定检查
        if "class " in code and "def __init__" in code:
            if "kwargs.pop" not in code and "**kwargs" in code:
                validation["suggestions"].append(
                    "重写 __init__ 时建议先 pop 自定义参数再调用 super().__init__(**kwargs)"
                )

        # 8. 无效方法检查（不会被父类调用的方法）
        invalid_methods = ["_rule_based_policy", "calculate_signals", "generate_signals"]
        for method in invalid_methods:
            if f"def {method}" in code:
                validation["warnings"].append(
                    f"方法 {method}() 不会被父类调用，如需自定义选股逻辑请覆写 generate_target_weight_position()"
                )

        # 9. 检查是否正确覆写了核心方法
        if "class " in code and "RedisTopkStrategy" in code:
            if "def generate_target_weight_position" not in code and "def generate_trade_decision" not in code:
                # 如果只是简单继承没有覆写任何方法，建议直接使用配置
                validation["suggestions"].append(
                    "如果不需要自定义选股逻辑，可以直接在 STRATEGY_CONFIG 中使用 RedisTopkStrategy，无需定义子类"
                )

        return validation


class QlibStrategyTemplates:
    """Qlib策略代码模板"""

    def generate_topk_strategy(
        self,
        design: dict[str, Any],
        requirement: dict[str, Any],
        is_dynamic: bool = False,
    ) -> str:
        """生成TopK Dropout策略（V2 合规：STRATEGY_CONFIG 入口 + RedisTopkStrategy 基类）"""

        strategy_name = requirement.get("strategy_name", "CustomTopkStrategy")
        strategy_desc = requirement.get("strategy_description", "")
        parameters = requirement.get("parameters", {})

        # 提取参数
        topk = parameters.get("topk", {}).get("value", 50) if isinstance(parameters.get("topk"), dict) else 50
        n_drop = parameters.get("n_drop", {}).get("value", 5) if isinstance(parameters.get("n_drop"), dict) else 5
        rebalance_days = parameters.get("rebalance_days", {}).get("value", 3) if isinstance(parameters.get("rebalance_days"), dict) else 3
        risk_mgmt = requirement.get("risk_management", {})
        account_stop_loss = risk_mgmt.get("account_stop_loss", 0.1)
        max_leverage = risk_mgmt.get("max_leverage", 1.0)

        # 自定义参数注入（用于需要自定义逻辑时）
        custom_init = ""
        custom_method = ""
        if is_dynamic:
            custom_init = "        self.dynamic_sizing = True"
            custom_method = """
    def generate_trade_decision(self, execute_result=None):
        \"\"\"基于全市场热度动态调整仓位的核心决策逻辑\"\"\"
        decision = super().generate_trade_decision(execute_result)
        # 动态仓位逻辑由平台 market_state_kwargs 注入，此处仅做示例
        return decision
"""

        code = f'''"""
自动生成的Qlib策略: {strategy_name}

策略描述: {strategy_desc}
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
动态仓位支持: {"已启用" if is_dynamic else "未启用"}
"""

from backend.services.engine.qlib_app.utils.extended_strategies import RedisTopkStrategy


def get_strategy_config():
    return {{
        "class": "RedisTopkStrategy",
        "module_path": "backend.services.engine.qlib_app.utils.extended_strategies",
        "kwargs": {{
            "signal": "<PRED>",
            "topk": {topk},
            "n_drop": {n_drop},
            "rebalance_days": {rebalance_days},
            "max_leverage": {max_leverage},
            "account_stop_loss": {account_stop_loss},
            "only_tradable": True,
        }}
    }}


STRATEGY_CONFIG = get_strategy_config()
'''
        return code

    def generate_weight_strategy(self, design: dict[str, Any], requirement: dict[str, Any]) -> str:
        """生成权重策略（V2 合规：STRATEGY_CONFIG 入口 + RedisWeightStrategy 基类）"""

        strategy_name = requirement.get("strategy_name", "CustomWeightStrategy")
        strategy_desc = requirement.get("strategy_description", "")
        parameters = requirement.get("parameters", {})
        risk_mgmt = requirement.get("risk_management", {})

        topk = parameters.get("topk", {}).get("value", 50) if isinstance(parameters.get("topk"), dict) else 50
        min_score = parameters.get("min_score", {}).get("value", 0.01) if isinstance(parameters.get("min_score"), dict) else 0.01
        max_weight = parameters.get("max_weight", {}).get("value", 0.1) if isinstance(parameters.get("max_weight"), dict) else 0.1
        rebalance_days = parameters.get("rebalance_days", {}).get("value", 3) if isinstance(parameters.get("rebalance_days"), dict) else 3
        account_stop_loss = risk_mgmt.get("account_stop_loss", 0.1)
        max_leverage = risk_mgmt.get("max_leverage", 1.0)

        code = f'''"""
自动生成的Qlib策略: {strategy_name}

策略描述: {strategy_desc}
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""


def get_strategy_config():
    return {{
        "class": "RedisWeightStrategy",
        "module_path": "backend.services.engine.qlib_app.utils.recording_strategy",
        "kwargs": {{
            "signal": "<PRED>",
            "topk": {topk},
            "min_score": {min_score},
            "max_weight": {max_weight},
            "rebalance_days": {rebalance_days},
            "max_leverage": {max_leverage},
            "account_stop_loss": {account_stop_loss},
            "only_tradable": True,
        }}
    }}


STRATEGY_CONFIG = get_strategy_config()
'''

        return code

    def generate_custom_strategy(self, design: dict[str, Any], requirement: dict[str, Any]) -> str:
        """生成自定义策略（V2 合规：STRATEGY_CONFIG 入口 + RedisRecordingStrategy 基类）"""

        strategy_name = requirement.get("strategy_name", "CustomStrategy")
        strategy_desc = requirement.get("strategy_description", "")
        parameters = requirement.get("parameters", {})
        risk_mgmt = requirement.get("risk_management", {})

        topk = parameters.get("topk", {}).get("value", 50) if isinstance(parameters.get("topk"), dict) else 50
        n_drop = parameters.get("n_drop", {}).get("value", 5) if isinstance(parameters.get("n_drop"), dict) else 5
        rebalance_days = parameters.get("rebalance_days", {}).get("value", 3) if isinstance(parameters.get("rebalance_days"), dict) else 3
        account_stop_loss = risk_mgmt.get("account_stop_loss", 0.1)
        max_leverage = risk_mgmt.get("max_leverage", 1.0)

        # 生成自定义参数赋值代码
        custom_param_assignments = []
        custom_param_pops = []
        for param_name, param_info in parameters.items():
            if isinstance(param_info, dict):
                default_val = param_info.get("value")
                if isinstance(default_val, str):
                    custom_param_pops.append(f'        self.{param_name} = kwargs.pop("{param_name}", "{default_val}")')
                else:
                    custom_param_pops.append(f'        self.{param_name} = kwargs.pop("{param_name}", {default_val})')

        pop_lines = "\n".join(custom_param_pops) if custom_param_pops else "        pass"
        assign_lines = "\n".join(custom_param_assignments) if custom_param_assignments else ""

        code = f'''"""
自动生成的Qlib策略: {strategy_name}

策略描述: {strategy_desc}
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

from backend.services.engine.qlib_app.utils.recording_strategy import RedisRecordingStrategy
from qlib.backtest.decision import TradeDecisionWO, Order, OrderDir
import pandas as pd
import numpy as np


class {strategy_name}(RedisRecordingStrategy):
    """
    {strategy_desc}

    策略类型: Custom Strategy (基于 RedisRecordingStrategy)
    """

    def __init__(self, **kwargs):
{pop_lines}
        super().__init__(**kwargs)

    def generate_trade_decision(self, execute_result=None):
        """
        生成交易决策 - 核心方法

        Returns:
            TradeDecisionWO: 交易决策对象
        """
        # 调用父类默认逻辑 (TopK 选股 + 换仓)
        return super().generate_trade_decision(execute_result)


def get_strategy_config():
    return {{
        "class": "{strategy_name}",
        "module_path": __name__,
        "kwargs": {{
            "signal": "<PRED>",
            "topk": {topk},
            "n_drop": {n_drop},
            "rebalance_days": {rebalance_days},
            "max_leverage": {max_leverage},
            "account_stop_loss": {account_stop_loss},
            "only_tradable": True,
        }}
    }}


STRATEGY_CONFIG = get_strategy_config()
'''

        return code

    def _generate_param_docs(self, parameters: dict[str, Any]) -> str:
        """生成参数文档"""
        docs = []
        for param_name, param_info in parameters.items():
            if isinstance(param_info, dict):
                desc = param_info.get("description", "参数")
                value = param_info.get("value", "N/A")
                range_info = param_info.get("range", [])

                doc = f"    - {param_name}: {desc} (默认: {value}"
                if range_info:
                    doc += f", 范围: {range_info[0]}-{range_info[1]}"
                doc += ")"
                docs.append(doc)

        return "\n".join(docs) if docs else "    无特殊参数"

    def _generate_init_params(self, parameters: dict[str, Any]) -> str:
        """生成初始化参数"""
        params = []
        for param_name, param_info in parameters.items():
            if isinstance(param_info, dict):
                default_value = param_info.get("value")
                if isinstance(default_value, str):
                    params.append(f'        {param_name}: str = "{default_value}"')
                else:
                    params.append(f"        {param_name}: float = {default_value}")
            else:
                params.append(f"        {param_name} = {param_info}")

        return ",\n".join(params) if params else "        # 无额外参数"

    def _generate_init_docs(self, parameters: dict[str, Any]) -> str:
        """生成初始化方法文档"""
        docs = []
        for param_name, param_info in parameters.items():
            if isinstance(param_info, dict):
                desc = param_info.get("description", "参数")
                docs.append(f"            {param_name}: {desc}")

        return "\n".join(docs) if docs else "            # 无额外参数"

    def _generate_param_assignments(self, parameters: dict[str, Any]) -> str:
        """生成参数赋值代码"""
        assignments = []
        for param_name in parameters.keys():
            assignments.append(f"        self.{param_name} = {param_name}")

        return "\n".join(assignments) if assignments else "        pass"
