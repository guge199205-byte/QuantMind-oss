from datetime import date

from backend.services.engine.ai_strategy.steps.step1_stock_selection import (
    FACTOR_COLUMN_MAP,
    _parse_dsl,
)
from backend.services.engine.ai_strategy.steps.step2_pool_confirmation import (
    _build_compat_table_sql,
    _build_pool_summary,
    _inject_trade_date_filter,
    _replace_table_with_compat_subquery,
)


def test_parse_dsl_supports_single_equals() -> None:
    conditions, combiners = _parse_dsl("SELECT symbol WHERE idx_hs300 = 1")

    assert combiners == []
    assert conditions == [{"type": "simple", "factor": "idx_hs300", "op": "=", "value": 1.0}]


def test_factor_mapping_uses_new_snapshot_columns() -> None:
    assert FACTOR_COLUMN_MAP["amount"] == "amount"
    assert FACTOR_COLUMN_MAP["is_hs300"] == "idx_hs300"
    assert FACTOR_COLUMN_MAP["is_csi1000"] == "idx_zz1000"


def test_inject_trade_date_filter_for_raw_sql() -> None:
    sql = "SELECT symbol FROM stock_daily_latest WHERE idx_hs300 = 1 ORDER BY total_mv DESC"

    normalized = _inject_trade_date_filter(sql, date(2026, 4, 30))

    assert "trade_date = '2026-04-30'" in normalized
    assert normalized.endswith("ORDER BY total_mv DESC")


def test_compat_subquery_exposes_old_and_new_column_aliases() -> None:
    columns = {
        "trade_date",
        "symbol",
        "name",
        "amount",
        "idx_hs300",
        "idx_zz1000",
        "close",
        "total_mv",
        "pe_ttm",
        "pb",
        "volume",
    }
    compat_sql = _build_compat_table_sql("stock_daily_latest", columns)
    rewritten = _replace_table_with_compat_subquery(
        "SELECT code as symbol, stock_name as name FROM stock_daily_latest WHERE is_csi300 = 1",
        "stock_daily_latest",
        compat_sql,
    )

    assert "symbol AS code" in compat_sql
    assert "name AS stock_name" in compat_sql
    assert "amount AS turnover" in compat_sql
    assert "idx_hs300 AS is_csi300" in compat_sql
    assert "FROM (SELECT" in rewritten


def test_pool_summary_uses_yi_buckets() -> None:
    class _Item:
        def __init__(self, market_cap: float) -> None:
            self.metrics = {"market_cap": market_cap}

    summary, charts = _build_pool_summary([_Item(80), _Item(150), _Item(300)], None, universe_total=10)

    assert summary["matchRate"] == 30.0
    assert charts["marketCap"] == [
        {"bucket": "<100亿", "value": 1},
        {"bucket": "100-200亿", "value": 1},
        {"bucket": ">=200亿", "value": 1},
    ]