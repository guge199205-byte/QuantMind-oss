"""Tests for the data dictionary loader."""

from backend.services.engine.strategy_lab.sdk.data_dict import (
    builtin_dictionary,
    DataDictionary,
    FeatureSpec,
)


def test_builtin_has_expected_features():
    dd = builtin_dictionary()
    names = dd.names()
    assert "momentum_20" in names
    assert "pe" in names
    assert "roe" in names
    assert "volatility_20" in names


def test_by_category_groups_correctly():
    dd = builtin_dictionary()
    cats = dd.by_category()
    assert "momentum" in cats
    assert "fundamental" in cats
    assert "momentum_20" in cats["momentum"]
    assert "pe" in cats["fundamental"]


def test_get_returns_spec():
    dd = builtin_dictionary()
    f = dd.get("momentum_20")
    assert isinstance(f, FeatureSpec)
    assert f.category == "momentum"
    assert dd.get("not_a_real_feature") is None


def test_to_payload_round_trip():
    dd = builtin_dictionary()
    payload = dd.to_payload()
    assert payload["total"] == len(dd.features)
    assert "categories" in payload
    assert payload["features"][0]["name"]
