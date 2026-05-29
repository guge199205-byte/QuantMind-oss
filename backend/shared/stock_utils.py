import re
from typing import Optional

class StockCodeUtil:
    """股票代码标准化工具类 (QuantMind 统一标准: SH600000)"""

    @staticmethod
    def to_prefix(code: str) -> str:
        """
        统一转换为 SH600000 格式 (Prefix型)

        Examples:
            - '600000.SH' -> 'SH600000'
            - 'sh600000' -> 'SH600000'
            - 'sz000001' -> 'SZ000001'
            - 'BJ830001' -> 'BJ830001'
        """
        if not code:
            return ""

        code = str(code).upper().strip()

        # 1. 已经是正确的 Prefix 格式 (SH/SZ/BJ + 6位数字)
        if re.match(r'^(SH|SZ|BJ)\d{6}$', code):
            return code

        # 2. 处理 Suffix 格式 (6位数字 + .SH/SZ/BJ)
        suffix_match = re.match(r'^(\d{6})\.(SH|SZ|BJ)$', code)
        if suffix_match:
            symbol, market = suffix_match.groups()
            return f"{market}{symbol}"

        # 3. 处理带点但位置反了的情况 (虽然少见)
        rev_suffix_match = re.match(r'^(SH|SZ|BJ)\.(\d{6})$', code)
        if rev_suffix_match:
            market, symbol = rev_suffix_match.groups()
            return f"{market}{symbol}"

        # 4. 处理纯 6 位数字 (基于号段尝试自动补全)
        digit_match = re.match(r'^(\d{6})$', code)
        if digit_match:
            symbol = digit_match.group(1)
            # 上海: 60, 68, 90
            if symbol.startswith(('60', '68', '90')):
                return f"SH{symbol}"
            # 深圳: 00, 30, 20
            elif symbol.startswith(('00', '30', '20')):
                return f"SZ{symbol}"
            # 北京: 83, 43, 87
            elif symbol.startswith(('83', '43', '87', '88')):
                return f"BJ{symbol}"
            return symbol # 无法识别保持原样

        return code

    @staticmethod
    def to_suffix(code: str) -> str:
        """
        统一转换为 600000.SH 格式 (Suffix型, 主要用于查询sdl等旧表)

        Examples:
            - 'SH600000' -> '600000.SH'
        """
        if not code:
            return ""

        code = str(code).upper().strip()

        # 1. 已经是正确的 Suffix 格式
        if re.match(r'^\d{6}\.(SH|SZ|BJ)$', code):
            return code

        # 2. 处理 Prefix 格式
        prefix_match = re.match(r'^(SH|SZ|BJ)(\d{6})$', code)
        if prefix_match:
            market, symbol = prefix_match.groups()
            return f"{symbol}.{market}"

        return code

    @staticmethod
    def normalize_list(codes: list[str]) -> list[str]:
        """批量标准化为 Prefix 格式"""
        return [StockCodeUtil.to_prefix(c) for c in codes if c]
