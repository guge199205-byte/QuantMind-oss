"""
测试SQL验证器的安全防护功能
"""

import sys
from pathlib import Path

import pytest

from backend.services.engine.ai_strategy.services.validators.sql_validator import (
    SQLValidationError,
    extract_table_names,
    safe_table_replace,
    sanitize_sql_identifier,
    validate_and_sanitize,
    validate_sql,
)

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


class TestSQLValidator:
    """SQL验证器测试套件"""

    def test_valid_select(self):
        """测试合法的SELECT语句"""
        sql = "SELECT symbol, name, close FROM stock_daily_latest WHERE close > 100"
        is_valid, msg = validate_sql(sql)
        assert is_valid is True
        assert msg == "验证通过"

    def test_reject_delete(self):
        """测试拒绝DELETE语句"""
        sql = "DELETE FROM stock_daily_latest WHERE symbol = 'TEST'"
        is_valid, msg = validate_sql(sql)
        assert is_valid is False
        assert "SELECT" in msg  # 提示仅允许SELECT

    def test_reject_drop(self):
        """测试拒绝DROP语句"""
        sql = "DROP TABLE stock_daily_latest"
        is_valid, msg = validate_sql(sql)
        assert is_valid is False
        assert "SELECT" in msg  # 提示仅允许SELECT

    def test_reject_union_injection(self):
        """测试拒绝UNION注入"""
        sql = "SELECT * FROM stock_daily_latest UNION SELECT password FROM users"
        is_valid, msg = validate_sql(sql)
        assert is_valid is False
        assert "UNION" in msg

    def test_reject_comment_injection(self):
        """测试拒绝注释注入"""
        sql = "SELECT * FROM stock_daily_latest -- WHERE close > 100"
        is_valid, msg = validate_sql(sql)
        assert is_valid is False
        assert "--" in msg

    def test_reject_unauthorized_table(self):
        """测试拒绝未授权的表"""
        sql = "SELECT * FROM users WHERE id = 1"
        is_valid, msg = validate_sql(sql)
        assert is_valid is False
        assert "未授权" in msg

    def test_reject_multiple_statements(self):
        """测试拒绝多语句执行"""
        sql = "SELECT * FROM stock_daily_latest WHERE close > 100; DROP TABLE users;"
        is_valid, msg = validate_sql(sql)
        assert is_valid is False
        # 会被第一步的SELECT检查或多语句检查拦截

    def test_reject_mismatched_quotes(self):
        """测试拒绝引号不匹配"""
        sql = "SELECT * FROM stock_daily_latest WHERE name = 'test"
        is_valid, msg = validate_sql(sql)
        assert is_valid is False
        assert "引号" in msg

    def test_extract_table_names(self):
        """测试提取表名"""
        sql = "SELECT a.* FROM stock_daily_latest a JOIN stock_basic b ON a.symbol = b.symbol"
        tables = extract_table_names(sql)
        assert "stock_daily_latest" in tables
        assert "stock_basic" in tables

    def test_sanitize_valid_identifier(self):
        """测试清理合法标识符"""
        result = sanitize_sql_identifier("stock_daily_latest")
        assert result == "stock_daily_latest"

    def test_sanitize_invalid_identifier(self):
        """测试拒绝非法标识符"""
        with pytest.raises(SQLValidationError):
            sanitize_sql_identifier("table'; DROP TABLE users--")

    def test_safe_table_replace(self):
        """测试安全的表名替换"""
        sql = "SELECT * FROM stock_daily WHERE close > 100"
        result = safe_table_replace(sql, "stock_daily", "stock_daily_latest")
        assert "stock_daily_latest" in result
        assert "WHERE" in result

    def test_safe_table_replace_unauthorized(self):
        """测试拒绝替换为未授权表"""
        sql = "SELECT * FROM stock_daily"
        with pytest.raises(SQLValidationError):
            safe_table_replace(sql, "stock_daily", "malicious_table")

    def test_validate_and_sanitize_adds_limit(self):
        """测试自动添加LIMIT"""
        sql = "SELECT * FROM stock_daily_latest WHERE close > 100"
        result = validate_and_sanitize(sql)
        assert "LIMIT" in result.upper()

    def test_validate_and_sanitize_removes_semicolon(self):
        """测试移除末尾分号"""
        sql = "SELECT * FROM stock_daily_latest LIMIT 100;"
        result = validate_and_sanitize(sql)
        assert not result.endswith(";")

    def test_reject_sql_length_limit(self):
        """测试SQL长度限制"""
        sql = "SELECT * FROM stock_daily_latest WHERE " + " AND ".join([f"col{i} > 0" for i in range(2000)])
        is_valid, msg = validate_sql(sql)
        assert is_valid is False
        assert "长度" in msg


class TestSQLInjectionVectors:
    """测试常见SQL注入向量"""

    def test_classic_or_injection(self):
        """测试经典 OR 注入（虽然参数化查询会防止，但验证器也要检测）"""
        sql = "SELECT * FROM stock_daily_latest WHERE symbol = 'TEST' OR '1'='1'"
        # 这个查询本身是合法SELECT，但应该通过参数化防止
        is_valid, _ = validate_sql(sql)
        # 验证器允许（因为是合法语法），但实际应用中用参数化
        assert is_valid is True

    def test_stacked_query_injection(self):
        """测试堆叠查询注入"""
        sql = "SELECT * FROM stock_daily_latest; INSERT INTO admin VALUES ('hacker', 'pass');"
        is_valid, msg = validate_sql(sql)
        assert is_valid is False

    def test_time_based_blind_injection(self):
        """测试时间盲注"""
        sql = "SELECT * FROM stock_daily_latest WHERE close > 100 AND SLEEP(5)"
        is_valid, msg = validate_sql(sql)
        assert is_valid is False
        assert "SLEEP" in msg

    def test_outfile_injection(self):
        """测试文件写入注入"""
        sql = "SELECT * FROM stock_daily_latest INTO OUTFILE '/tmp/hack.txt'"
        is_valid, msg = validate_sql(sql)
        assert is_valid is False
        assert "OUTFILE" in msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
