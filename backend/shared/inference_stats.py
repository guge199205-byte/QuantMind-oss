"""推理结果分数分布统计 helper。

供 `/models/inference/runs/{run_id}` 与 admin `/admin/models/predictions/{run_id}` 共用，
让前端排名 Drawer 在 6000+ 股票的列表上方有一个"整体方向感"指标。
"""

from __future__ import annotations

import statistics
from typing import Any


def _bucket_histogram(sorted_scores: list[float], bins: int = 20) -> list[dict[str, Any]]:
    """对已排序的分数列表做等宽分桶。

    最后一个桶闭区间包含 max；其他桶半开。返回 [{x0,x1,count}, ...]。
    """
    n = len(sorted_scores)
    if n == 0:
        return []
    lo = sorted_scores[0]
    hi = sorted_scores[-1]
    if hi == lo:
        return [{"x0": lo, "x1": hi, "count": n}]

    width = (hi - lo) / bins
    buckets: list[dict[str, Any]] = []
    for i in range(bins):
        x0 = lo + i * width
        x1 = hi if i == bins - 1 else lo + (i + 1) * width
        buckets.append({"x0": round(x0, 6), "x1": round(x1, 6), "count": 0})

    j = 0
    for s in sorted_scores:
        while j < bins - 1 and s >= buckets[j]["x1"]:
            j += 1
        buckets[j]["count"] += 1
    return buckets


def compute_score_distribution(scores: list[float]) -> dict[str, Any] | None:
    """计算分数分布统计。

    参数 scores 不需要预先排序；None/NaN 由调用方过滤。
    返回 dict 字段供前端 ScoreDistributionPanel 直接渲染。
    """
    if not scores:
        return None
    n = len(scores)
    pos = sum(1 for s in scores if s > 0)
    neg = sum(1 for s in scores if s < 0)
    zero = n - pos - neg
    sorted_s = sorted(scores)

    def pct(p: float) -> float:
        idx = max(0, min(n - 1, int(round(p * (n - 1)))))
        return float(sorted_s[idx])

    return {
        "count": n,
        "positive_count": pos,
        "positive_pct": round(pos / n * 100, 2),
        "negative_count": neg,
        "negative_pct": round(neg / n * 100, 2),
        "zero_count": zero,
        "zero_pct": round(zero / n * 100, 2),
        "mean": round(statistics.fmean(scores), 6),
        "median": round(statistics.median(scores), 6),
        "stdev": round(statistics.pstdev(scores), 6) if n > 1 else 0.0,
        "p10": pct(0.10),
        "p25": pct(0.25),
        "p75": pct(0.75),
        "p90": pct(0.90),
        "min": sorted_s[0],
        "max": sorted_s[-1],
        "histogram": _bucket_histogram(sorted_s, bins=20),
    }
