"""
SQL安全验证模块
防止SQL注入和危险操作
"""

import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)

# 允许的表名白名单
ALLOWED_TABLES = {
    "stock_daily_latest",
    "stock_daily",
    "stock_selection",
    "stock_basic",
    "user_universe",
}

# 禁止的SQL关键字（黑名单）
DANGEROUS_KEYWORDS = [
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "TRUNCATE",
    "ALTER",
    "CREATE",
    "RENAME",
    "REPLACE",
    "GRANT",
    "REVOKE",
    "EXECUTE",
    "EXEC",
    "CALL",
    "PROCEDURE",
    "FUNCTION",
    "TRIGGER",
    "CURSOR",
    "DECLARE",
    "MERGE",
    "LOAD",
    "OUTFILE",
    "INFILE",
    "DUMPFILE",
    # 防止注释注入
    "--",
    "/*",
    "*/",
    # 防止联合查询注入
    "UNION",
    # 防止时间/盲注
    "SLEEP",
    "BENCHMARK",
    "WAITFOR",
]

# 允许的SELECT语句列名模式（白名单字段前缀）
ALLOWED_COLUMN_PATTERNS = [
    r"^symbol$",
    r"^code$",
    r"^name$",
    r"^stock_name$",
    r"^trade_date$",
    r"^close$",
    r"^open$",
    r"^high$",
    r"^low$",
    r"^volume$",
    r"^amount$",
    r"^turnover$",
    r"^turnover_rate$",
    r"^pct_change$",
    r"^total_mv$",
    r"^market_cap$",
    r"^pe_ttm$",
    r"^pe_ratio$",
    r"^pb$",
    r"^pb_ratio$",
    r"^ps_ratio$",
    r"^roe$",
    r"^net_profit_growth$",
    r"^industry$",
    r"^is_st$",
    r"^idx_hs300$",
    r"^is_hs300$",
    r"^is_csi300$",
    r"^idx_zz1000$",
    r"^is_csi1000$",
    r"^is_suspended$",
    r"^is_listed_over_1y$",
    r"^rsi$",
    r"^macd_",
    r"^kdj_",
    r"^sma\d+$",
    r"^ema\d+$",
    r"^\*$",  # 允许 SELECT *
]


class SQLValidationError(Exception):
    """SQL验证异常"""

    pass


def validate_sql(sql: str, allow_star: bool = True) -> tuple[bool, str]:
    """
    验证SQL语句的安全性

    Args:
        sql: 待验证的SQL语句
        allow_star: 是否允许SELECT *

    Returns:
        (是否通过, 错误信息)

    Raises:
        SQLValidationError: 验证失败时抛出
    """
    if not sql or not sql.strip():
        return False, "SQL语句不能为空"

    sql_upper = sql.upper().strip()

    # 1. 验证必须是SELECT语句
    if not sql_upper.startswith("SELECT"):
        return False, "仅允许SELECT查询语句"

    # 2. 检查危险关键字
    for keyword in DANGEROUS_KEYWORDS:
        if keyword in sql_upper:
            logger.warning(f"SQL包含危险关键字: {keyword}")
            return False, f"SQL包含禁止的操作: {keyword}"

    # 3. 验证表名白名单
    table_names = extract_table_names(sql)
    for table in table_names:
        if table.lower() not in ALLOWED_TABLES:
            logger.warning(f"SQL引用未授权表: {table}")
            return False, f"未授权访问表: {table}"

    # 4. 验证没有多语句（防止';'分隔的多个SQL）
    # 排除LIMIT子句后的分号
    sql_without_limit = re.sub(r"LIMIT\s+\d+\s*;?\s*$", "", sql_upper, flags=re.IGNORECASE)
    if ";" in sql_without_limit:
        return False, "不允许执行多条SQL语句"

    # 5. 验证括号匹配（防止注入）
    if sql.count("(") != sql.count(")"):
        return False, "SQL语句括号不匹配"

    # 6. 验证引号匹配
    single_quote_count = sql.count("'")
    double_quote_count = sql.count('"')
    if single_quote_count % 2 != 0 or double_quote_count % 2 != 0:
        return False, "SQL语句引号不匹配"

    # 7. 限制SQL长度（防止DoS）
    if len(sql) > 10000:
        return False, "SQL语句长度超过限制(10000字符)"

    logger.debug(f"SQL validation passed: {sql[:100]}...")
    return True, "验证通过"


def extract_table_names(sql: str) -> list[str]:
    """
    从SQL语句中提取表名

    Args:
        sql: SQL语句

    Returns:
        表名列表
    """
    tables = []

    # 匹配 FROM table_name 和 JOIN table_name
    from_pattern = r"\bFROM\s+([a-zA-Z0-9_]+)"
    join_pattern = r"\bJOIN\s+([a-zA-Z0-9_]+)"

    from_matches = re.finditer(from_pattern, sql, re.IGNORECASE)
    join_matches = re.finditer(join_pattern, sql, re.IGNORECASE)

    for match in from_matches:
        tables.append(match.group(1))

    for match in join_matches:
        tables.append(match.group(1))

    return tables


def sanitize_sql_identifier(identifier: str) -> str:
    """
    清理SQL标识符（表名、列名），防止注入

    Args:
        identifier: 标识符字符串

    Returns:
        清理后的标识符

    Raises:
        SQLValidationError: 标识符不合法时抛出
    """
    # 只允许字母、数字、下划线
    if not re.match(r"^[a-zA-Z0-9_]+$", identifier):
        raise SQLValidationError(f"非法的SQL标识符: {identifier}")

    # 长度限制
    if len(identifier) > 64:
        raise SQLValidationError(f"标识符长度超过限制: {identifier}")

    return identifier


def safe_table_replace(sql: str, old_table: str, new_table: str) -> str:
    """
    安全的表名替换

    Args:
        sql: 原始SQL
        old_table: 旧表名
        new_table: 新表名

    Returns:
        替换后的SQL

    Raises:
        SQLValidationError: 表名不合法时抛出
    """
    # 验证表名合法性
    sanitize_sql_identifier(old_table)
    sanitize_sql_identifier(new_table)

    # 确保新表在白名单中
    if new_table.lower() not in ALLOWED_TABLES:
        raise SQLValidationError(f"目标表不在白名单中: {new_table}")

    # 使用正则替换，确保边界匹配
    pattern = rf"\b{re.escape(old_table)}\b"
    replaced_sql = re.sub(pattern, new_table, sql, flags=re.IGNORECASE)

    return replaced_sql


def validate_and_sanitize(sql: str) -> str:
    """
    验证并清理SQL语句（一站式接口）

    Args:
        sql: 原始SQL

    Returns:
        清理后的SQL

    Raises:
        SQLValidationError: 验证失败时抛出
    """
    # 1. 基础验证
    is_valid, error_msg = validate_sql(sql)
    if not is_valid:
        raise SQLValidationError(error_msg)

    # 2. 移除多余的空白字符
    sql = " ".join(sql.split())

    # 3. 确保有LIMIT子句（防止返回过多数据）
    if "LIMIT" not in sql.upper():
        sql += " LIMIT 1000"

    # 4. 移除末尾分号
    sql = sql.rstrip(";").strip()

    return sql
