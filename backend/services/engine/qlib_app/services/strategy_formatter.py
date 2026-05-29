import ast
import logging
from typing import Optional

from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

logger = logging.getLogger(__name__)
task_logger = StructuredTaskLogger(logger, "StrategyFormatterService")


class StrategyFormatterService:
    """Strategy formatting middleware for filtering and patching unsupported Qlib strategies."""

    def format_and_repair(self, content: str) -> str:
        """
        Formats and repairs third party strategy code to be compatible with the system
        1. Fix deprecated imports
        2. Append a get_strategy_config() function if not present with parameter auto-repair
        """
        if not content or not content.strip():
            return content

        # 1. Patch legacy imports via simple string replacement
        import_patches = {
            "from qlib.contrib.strategy import": "from qlib.strategy.base import",
            "import qlib.contrib.strategy": "import qlib.strategy.base",
            "from qlib.contrib.strategy.base import": "from qlib.strategy.base import",
        }
        for old, new in import_patches.items():
            content = content.replace(old, new)

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            task_logger.warning(
                "ast_parse_skipped",
                "Strategy formatter skipped AST analysis due to SyntaxError",
                error=str(e),
            )
            return content

        has_base_strategy_import = False
        strategy_class_node = None
        has_strategy_info = False

        # Scan the AST for classes and configuration protocols
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                if node.module in ["qlib.strategy.base", "qlib.contrib.strategy", "qlib.contrib.strategy.base"]:
                    for n in node.names:
                        if n.name == "BaseStrategy":
                            has_base_strategy_import = True
            elif isinstance(node, ast.ClassDef):
                # Prefer classes that inherit from BaseStrategy or have 'Strategy' in their name
                is_strategy = False
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "BaseStrategy":
                        is_strategy = True
                        break
                if is_strategy or "Strategy" in node.name:
                    strategy_class_node = node
                # Fallback to the first class if none match carefully
                elif strategy_class_node is None:
                    strategy_class_node = node
            elif isinstance(node, ast.Assign):
                # Check for STRATEGY_CONFIG
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "STRATEGY_CONFIG":
                        has_strategy_info = True
            elif isinstance(node, ast.FunctionDef):
                # Check for get_strategy_config or get_strategy_instance
                if node.name in ["get_strategy_config", "get_strategy_instance"]:
                    has_strategy_info = True

        # If no strategy class could be inferred, we cannot adapt it automatically
        if not strategy_class_node:
            task_logger.info("no_class_detected", "No class detected in content")
            return content

        # Parameter Auto-Repair Detection
        init_kwargs = {}
        for sub_node in strategy_class_node.body:
            if isinstance(sub_node, ast.FunctionDef) and sub_node.name == "__init__":
                # Extract mandatory arguments (those without default values)
                # sub_node.args.args contains all arguments including 'self'
                # sub_node.args.defaults contains default values for the LAST n arguments
                all_args = [arg.arg for arg in sub_node.args.args if arg.arg != "self"]
                defaults_count = len(sub_node.args.defaults)

                # Mandatory args are the ones at the beginning that don't have a matching default
                mandatory_args = all_args[:-defaults_count] if defaults_count > 0 else all_args

                # Assign safe defaults for common Qlib params often seen in legacy strategies
                safe_defaults = {
                    "signal": "<PRED>",
                    "topk": 50,
                    "n_drop": 5,
                    "pool_file_key": "",
                    "pool_file_url": "",
                    "condition": {},
                    "position_config": {},
                    "style_params": {},
                }

                for arg in mandatory_args:
                    init_kwargs[arg] = safe_defaults.get(arg, None)
                break

        lines = content.split("\n")

        # 2. Add BaseStrategy import if missing
        if not has_base_strategy_import:
            lines.insert(0, "from qlib.strategy.base import BaseStrategy")

        # 3. Generate connection boilerplate if no existing configuration exports found
        if not has_strategy_info:
            class_name = strategy_class_node.name
            task_logger.info(
                "inject_get_strategy_config",
                "Auto-injecting get_strategy_config",
                class_name=class_name,
                repaired_params=len(init_kwargs),
            )

            import json

            kwargs_str = json.dumps(init_kwargs, indent=8).strip()

            wrapper_code = f"""
# === System Auto-Injected Adapter Module ===
def get_strategy_config():
    return {{
        "class": "{class_name}",
        "module_path": "",
        "kwargs": {kwargs_str}
    }}
"""
            lines.append(wrapper_code)

        # 4. Inject TradeDecision compatibility wrapper for ALL detected strategy classes
        class_name = strategy_class_node.name
        compat_wrapper = f"""
# === TradeDecision Compatibility Wrapper ===
try:
    from qlib.backtest.decision import TradeDecisionWO, Order
    
    def _ensure_trade_decision(self, *args, **kwargs):
        # Call the original method
        res = self._original_generate_trade_decision(*args, **kwargs)
        if isinstance(res, (dict, list)):
            order_list = []
            if isinstance(res, dict):
                for stock, amount in res.items():
                    if isinstance(amount, (int, float)):
                        order_list.append(Order(
                            stock_id=stock, 
                            amount=abs(float(amount)), 
                            start_time=None, 
                            end_time=None, 
                            direction=Order.BUY if amount > 0 else Order.SELL
                        ))
            else:
                order_list = res
            return TradeDecisionWO(order_list, self)
        return res

    if hasattr({class_name}, 'generate_trade_decision'):
        # Check if already wrapped to avoid infinite recursion if re-formatted
        if not hasattr({class_name}, '_original_generate_trade_decision'):
            {class_name}._original_generate_trade_decision = {class_name}.generate_trade_decision
            {class_name}.generate_trade_decision = _ensure_trade_decision
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(
        "Failed to inject TradeDecision compatibility wrapper: {{}}".format(e)
    )
"""
        lines.append(compat_wrapper)

        return "\n".join(lines)
