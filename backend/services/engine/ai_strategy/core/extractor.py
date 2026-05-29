import ast
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class StrategyConfigExtractor:
    """
    策略配置提取器
    通过 AST 静态分析 Python 策略文件，提取其中的 STRATEGY_CONFIG 字典。
    这种方法比直接 exec() 更安全，适合大规模高并发下的策略预处理。
    """

    @staticmethod
    def extract(code: str) -> dict[str, Any]:
        """
        从 Python 代码字符串中提取 STRATEGY_CONFIG 字典
        """
        try:
            tree = ast.parse(code)

            # 1. 查找 STRATEGY_CONFIG 的直接赋值语句
            config = StrategyConfigExtractor._find_assignment(tree, "STRATEGY_CONFIG")
            if config:
                return config

            # 2. 如果没找到直接赋值，查找 get_strategy_config 函数并尝试解析其返回的字典
            config = StrategyConfigExtractor._find_function_return(tree, "get_strategy_config")
            if config:
                return config

            raise ValueError("未在代码中找到有效的 STRATEGY_CONFIG 定义或 get_strategy_config 函数")

        except SyntaxError as e:
            logger.error(f"代码语法错误，无法解析: {e}")
            raise ValueError(f"代码语法错误: {e.msg}")
        except Exception as e:
            logger.error(f"提取策略配置失败: {e}", exc_info=True)
            raise ValueError(f"配置提取失败: {str(e)}")

    @staticmethod
    def _find_assignment(tree: ast.AST, target_name: str) -> dict[str, Any] | None:
        """查找 top-level 的变量赋值"""
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == target_name:
                        return StrategyConfigExtractor._eval_node(node.value)
        return None

    @staticmethod
    def _find_function_return(tree: ast.AST, func_name: str) -> dict[str, Any] | None:
        """查找特定函数的 return 语句中的字典"""
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                for subnode in node.body:
                    if isinstance(subnode, ast.Return) and isinstance(subnode.value, ast.Dict):
                        return StrategyConfigExtractor._eval_node(subnode.value)
        return None

    @staticmethod
    def _eval_node(node: ast.AST) -> Any:
        """
        安全地将 AST 节点转换为 Python 基本类型
        限制仅支持：字典、列表、字符串、数字、布尔值、None
        """
        if isinstance(node, ast.Constant):  # Python 3.8+
            return node.value
        elif isinstance(node, ast.Dict):
            return {
                StrategyConfigExtractor._eval_node(k): StrategyConfigExtractor._eval_node(v)
                for k, v in zip(node.keys, node.values)
                if k is not None
            }
        elif isinstance(node, ast.List):
            return [StrategyConfigExtractor._eval_node(el) for el in node.elts]
        elif isinstance(node, ast.Name):
            # 处理布尔值和 None
            constants = {"True": True, "False": False, "None": None}
            if node.id in constants:
                return constants[node.id]
            return f"<{node.id}>"  # 对于无法静态解析的变量，返回占位符
        elif isinstance(node, ast.BinOp):
            # 简单的二元运算（如字符串拼接或数字加减）在此处可以扩展，暂不实现
            return "<Expression>"
        else:
            return None


if __name__ == "__main__":
    # 测试代码
    test_code = """
def get_strategy_config():
    return {
        "class": "RedisRecordingStrategy",
        "kwargs": {
            "topk": 50,
            "signal": "<PRED>",
            "dynamic_position": True
        }
    }
STRATEGY_CONFIG = get_strategy_config()
"""
    try:
        res = StrategyConfigExtractor.extract(test_code)
        print(f"提取结果: {res}")
    except Exception as exc:
        print(f"错误: {exc}")
