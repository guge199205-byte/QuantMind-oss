"""Tests for the parquet-aware loader and JSON payload writer."""

from pathlib import Path

import pytest

from backend.services.engine.strategy_lab.sdk import data_dict


def test_load_dictionary_with_missing_dir_returns_builtin(tmp_path: Path):
    dd = data_dict.load_dictionary(tmp_path / "nope")
    assert "momentum_20" in dd.names()
    assert dd.parquet_columns == []


def test_load_dictionary_overlays_parquet_columns(tmp_path: Path):
    pq = pytest.importorskip("pyarrow.parquet")
    pa = pytest.importorskip("pyarrow")

    table = pa.table(
        {
            "trade_date": ["2025-01-01"],
            "symbol": ["SH600036"],
            # known feature already in builtin -> should not duplicate
            "momentum_20": [0.1],
            # unknown feature -> should be appended as 'other'
            "weird_feat_42": [0.5],
        }
    )
    out = tmp_path / "model_features_2025.parquet"
    pq.write_table(table, str(out))

    dd = data_dict.load_dictionary(tmp_path)
    assert "weird_feat_42" in dd.names()
    spec = dd.get("weird_feat_42")
    assert spec is not None and spec.category == "other"
    # Builtin not duplicated
    assert dd.names().count("momentum_20") == 1
    assert "trade_date" in dd.parquet_columns


def test_write_payload(tmp_path: Path):
    out = tmp_path / "payload.json"
    data_dict.write_payload(out)
    txt = out.read_text(encoding="utf-8")
    assert "momentum_20" in txt
    assert "categories" in txt
