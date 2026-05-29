import re
from typing import List, Tuple


class DiffParser:
    """
    解析 SEARCH/REPLACE 块协议。
    """

    @staticmethod
    def parse_blocks(content: str) -> list[tuple[str, str]]:
        """
        从 LLM 输出中提取所有 SEARCH/REPLACE 块
        """
        # 使用更稳健的正则匹配
        pattern = r"<<<< SEARCH\s*\n(.*?)\n====\n(.*?)\n>>>>"
        matches = re.findall(pattern, content, re.DOTALL)
        return matches

    @staticmethod
    def apply_diff(original_code: str, search_text: str, replace_text: str) -> str:
        """
        将单个替换应用到原始代码中。
        """
        if not search_text.strip():
            return original_code + "\n" + replace_text

        return original_code.replace(search_text, replace_text)
