"""Tests for engine.data_provider — symbol normalization + InMemoryProvider."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.services.engine.strategy_lab.engine.data_provider import (
    InMemoryProvider,
    QlibProvider,
    data_snapshot_at,
    load_universe,
    to_internal,
    to_qlib,
)


def test_symbol_normalization():
    assert to_qlib("SH600036") == "sh600036"
    assert to_qlib("600036.SH") == "sh600036"
    assert to_qlib("00700.HK") == "hk00700"
    assert to_internal("600036.SH") == "SH600036"
    assert to_internal("SH600036") == "SH600036"


def _df(closes: list[float], start: str = "2025-01-02") -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=len(closes), freq="B")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [1000.0] * len(closes),
            "adj_close": closes,
        },
        index=idx,
    )


def test_inmemory_history_single_symbol():
    p = InMemoryProvider({"SH600036": _df([10.0, 10.5, 11.0, 11.5, 12.0])})
    s = p.history(symbol="SH600036", n=3, today=pd.Timestamp("2025-01-08"))
    assert len(s) == 3
    assert float(s.iloc[-1]) == 12.0


def test_inmemory_history_multi_symbol_dataframe():
    p = InMemoryProvider(
        {
            "A": _df([1.0, 2.0, 3.0]),
            "B": _df([4.0, 5.0, 6.0]),
        }
    )
    df = p.history(symbols=["A", "B"], n=2, today=pd.Timestamp("2025-01-06"))
    assert "A" in df.columns and "B" in df.columns


def test_inmemory_history_missing_symbol_returns_empty():
    p = InMemoryProvider({})
    s = p.history(symbol="UNKNOWN", n=5, today=pd.Timestamp("2025-01-08"))
    assert s.empty


def test_inmemory_history_no_args_returns_empty():
    p = InMemoryProvider({"A": _df([1.0])})
    s = p.history()
    assert s.empty


def test_inmemory_feature_lookup():
    df = _df([10.0, 10.5])
    df["momentum_5"] = [0.01, 0.03]
    p = InMemoryProvider({"X": df})
    val = p.feature("X", "momentum_5", today=pd.Timestamp("2025-01-03"))
    assert val == 0.03

    arr = p.feature("X", "momentum_5", n=2, today=pd.Timestamp("2025-01-03"))
    assert len(arr) == 2

    # Unknown feature falls through to feature_lookup
    p2 = InMemoryProvider(
        {"X": _df([1.0])},
        feature_lookup={("X", pd.Timestamp("2025-01-02")): {"alpha": 0.5}},
    )
    assert p2.feature("X", "alpha", today=pd.Timestamp("2025-01-02")) == 0.5
    assert p2.feature("X", "missing", today=pd.Timestamp("2025-01-02")) is None


def test_inmemory_list_features_excludes_ohlcv():
    df = _df([10.0])
    df["alpha_1"] = [0.5]
    p = InMemoryProvider({"A": df})
    feats = p.list_features()
    assert "alpha_1" in feats
    assert "close" not in feats


def test_inmemory_snapshot_returns_last_row_per_symbol():
    p = InMemoryProvider({"A": _df([1.0, 2.0]), "B": _df([3.0, 4.0])})
    snap = p.snapshot(date=pd.Timestamp("2025-01-06"), symbols=["A", "B"])
    assert "close" in snap.columns
    assert snap.loc["A", "close"] == 2.0


def test_inmemory_snapshot_no_date_returns_empty():
    p = InMemoryProvider({"A": _df([1.0])})
    assert p.snapshot().empty


def test_inmemory_benchmark_history_default():
    p = InMemoryProvider({}, benchmark_series=pd.Series([1.0, 2.0, 3.0],
        index=pd.date_range("2025-01-02", periods=3, freq="B")))
    s = p.benchmark_history("SH000300", 2, pd.Timestamp("2025-01-06"))
    assert len(s) == 2

    # No benchmark configured -> empty
    p2 = InMemoryProvider({})
    assert p2.benchmark_history("SH000300", 5, None).empty


def test_inmemory_helpers():
    p = InMemoryProvider({})
    assert p.is_st("X") is False
    assert p.is_tradable("X") is True


def test_load_universe_missing_file(tmp_path):
    assert load_universe("nope", str(tmp_path)) == []


def test_load_universe_reads_instruments(tmp_path):
    inst = tmp_path / "instruments"
    inst.mkdir()
    (inst / "csi300.txt").write_text("sh600036\t2010-01-01\t2025-01-01\nsz000001\t2010-01-01\t2025-01-01\n")
    syms = load_universe("csi300", str(tmp_path))
    assert "SH600036" in syms
    assert "SZ000001" in syms


def test_data_snapshot_at_reads_last_calendar_date(tmp_path):
    cal = tmp_path / "calendars"
    cal.mkdir()
    (cal / "day.txt").write_text("2025-01-02\n2025-01-03\n2025-06-12\n")
    assert data_snapshot_at(str(tmp_path)) == "2025-06-12"


def test_data_snapshot_at_missing_returns_none(tmp_path):
    assert data_snapshot_at(str(tmp_path)) is None


def test_qlib_provider_constructs_lazily():
    qp = QlibProvider(data_path="/nonexistent/path")
    assert qp._initialised is False
    assert qp._D is None
