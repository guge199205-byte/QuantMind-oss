"""Feature data dictionary — 152-dim parquet feature metadata loader.

The runtime reads metadata once at startup, exposes it to the SDK as
``ctx.list_features()`` and to the AI assistant as the ``get_data_dict()``
tool. We keep the catalog static here; the parquet schema is the source of
truth, and we cross-check at runner startup.

See docs/QuantMind_152维特征方案规范.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Default feature parquet location (read-only mounted in sandbox).
FEATURE_PARQUET_DIR = Path("/app/db/feature_snapshots")


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    category: str
    description: str = ""
    unit: str = ""
    direction: str = ""
    is_forward_safe: bool = True


# Curated subset — the runner overlays the actual parquet column list at boot.
# Keeping a static seed lets unit tests run without touching the filesystem.
_BUILTIN_FEATURES: tuple[FeatureSpec, ...] = (
    # Price / momentum
    FeatureSpec("momentum_5", "momentum", "5 日收益率", "ratio"),
    FeatureSpec("momentum_10", "momentum", "10 日收益率", "ratio"),
    FeatureSpec("momentum_20", "momentum", "20 日收益率", "ratio"),
    FeatureSpec("momentum_60", "momentum", "60 日收益率", "ratio"),
    # Volatility
    FeatureSpec("volatility_20", "volatility", "20 日年化波动率", "ratio"),
    FeatureSpec("atr_14", "volatility", "14 日 ATR", "price"),
    # Liquidity
    FeatureSpec("turnover_20", "liquidity", "20 日平均换手率", "ratio"),
    FeatureSpec("amihud_20", "liquidity", "20 日 Amihud 流动性", "scaled"),
    # Fundamentals
    FeatureSpec("pe", "fundamental", "市盈率 TTM", "x"),
    FeatureSpec("pb", "fundamental", "市净率 LF", "x"),
    FeatureSpec("ps", "fundamental", "市销率 TTM", "x"),
    FeatureSpec("roe", "fundamental", "净资产收益率", "ratio"),
    # Fund flow
    FeatureSpec("net_inflow_5", "fund_flow", "5 日主力净流入", "amount"),
    FeatureSpec("net_inflow_20", "fund_flow", "20 日主力净流入", "amount"),
    # Style
    FeatureSpec("size", "style", "对数市值", "log"),
    FeatureSpec("beta", "style", "60 日 beta", "scalar"),
)


@dataclass
class DataDictionary:
    features: list[FeatureSpec] = field(default_factory=list)
    parquet_columns: list[str] = field(default_factory=list)

    # ---- queries ----
    def names(self) -> list[str]:
        return sorted({f.name for f in self.features})

    def by_category(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for f in self.features:
            out.setdefault(f.category, []).append(f.name)
        for k in out:
            out[k].sort()
        return out

    def get(self, name: str) -> FeatureSpec | None:
        for f in self.features:
            if f.name == name:
                return f
        return None

    def to_payload(self) -> dict:
        return {
            "features": [
                {
                    "name": f.name,
                    "category": f.category,
                    "description": f.description,
                    "unit": f.unit,
                    "direction": f.direction,
                    "is_forward_safe": f.is_forward_safe,
                }
                for f in self.features
            ],
            "categories": self.by_category(),
            "total": len(self.features),
        }


def builtin_dictionary() -> DataDictionary:
    """Return the curated builtin feature dictionary (no IO)."""
    return DataDictionary(features=list(_BUILTIN_FEATURES))


def load_dictionary(parquet_dir: Path | None = None) -> DataDictionary:
    """Load the dictionary, overlaying with actual parquet columns when available."""
    parquet_dir = parquet_dir or FEATURE_PARQUET_DIR
    dd = builtin_dictionary()

    if not parquet_dir.exists():
        return dd

    try:
        import pyarrow.parquet as pq

        sample: Path | None = next(iter(sorted(parquet_dir.glob("model_features_*.parquet"))), None)
        if sample is None:
            return dd
        meta = pq.ParquetFile(str(sample)).metadata
        cols = [meta.schema.column(i).name for i in range(meta.num_columns)]
        dd.parquet_columns = cols

        known = {f.name for f in dd.features}
        for c in cols:
            if c in known:
                continue
            if c in {"trade_date", "symbol", "market"}:
                continue
            dd.features.append(
                FeatureSpec(name=c, category="other", description="(未编目)")
            )
    except Exception:
        return dd

    return dd


def write_payload(out_path: Path, dd: DataDictionary | None = None) -> None:
    """Dump the dictionary as JSON (used by the AI assistant tool)."""
    dd = dd or builtin_dictionary()
    out_path.write_text(json.dumps(dd.to_payload(), ensure_ascii=False, indent=2))
