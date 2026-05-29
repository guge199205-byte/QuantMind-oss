from backend.shared.schema_registry import (
    detect_duplicate_tables,
    list_schema_keys,
    load_registered_schemas,
)


def test_schema_registry_contains_core_keys():
    keys = set(list_schema_keys())
    assert "api.community" in keys
    assert "api.user" in keys
    assert "trade.core" in keys
    assert "trade.simulation" in keys
    assert "trade.portfolio" in keys
    assert "stream.market" in keys


def test_schema_registry_has_no_duplicate_table_names():
    duplicates = detect_duplicate_tables()
    assert duplicates == {}


def test_trade_schemas_load_with_tables():
    schemas = load_registered_schemas(("trade.core", "trade.simulation", "trade.portfolio"))
    table_count = sum(len(schema.metadata.tables) for schema in schemas)
    assert table_count > 0
