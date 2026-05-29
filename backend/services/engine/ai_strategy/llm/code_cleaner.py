"""LLM 生成代码的清理工具"""

import re


def strip_markdown_fences(code: str) -> str:
    """将 LLM 返回的 markdown 代码围栏剥离为纯 Python。

    常见问题：LLM 返回 ```python ...```，直接 ast.parse 会在第 1 行报 invalid syntax。

    从 steps/step5_generation.py._strip_markdown_fences 提取。
    """
    if not code:
        return code
    s = code.strip()
    if "```" not in s:
        return s + "\n"

    # Prefer the first fenced block if present.
    try:
        m = re.search(r"```(?:python)?\s*(.*?)\s*```", s, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return (m.group(1) or "").strip() + "\n"
    except Exception:
        pass

    # Fallback: drop fence lines.
    lines = [ln for ln in s.splitlines() if not ln.strip().startswith("```")]
    return "\n".join(lines).strip() + "\n"


def clean_strategy_code(code: str) -> str:
    """清理策略代码：剥离 markdown 围栏并规范化末尾换行。"""
    cleaned = strip_markdown_fences(code)
    # 确保文件以单个换行符结尾
    return cleaned.rstrip() + "\n" if cleaned else ""
