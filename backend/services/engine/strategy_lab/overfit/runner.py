"""4-gate overfit detection runner.

Each gate runs the user's strategy in-process by invoking ``run_backtest``
(no subprocess). The outer FastAPI handler is responsible for:
  - AST-checking the code first
  - Bounding total wall time (gates can sweep up to ~10 backtests)

Gate semantics
--------------
gate1_train_test
    Split window into 70/30 train/test by date. Pass if test sharpe ≥ 0.6 ×
    train sharpe and test cum_return > 0. Score 0..100.

gate2_walkforward
    3 rolling folds: train [0..0.5], test (0.5..0.7]; train [0..0.7], test
    (0.7..0.85]; train [0..0.85], test (0.85..1.0]. Pass if at least 2 folds
    have test sharpe > 0.

gate3_param_sense
    For each ``ctx.param`` declared, perturb to nearest neighbours in its
    ``choices`` list (or ±20% for numeric default-only params). Pass if
    sharpe variance across perturbations < 0.5 × baseline sharpe.

gate4_monte_carlo
    Bootstrap-shuffle the daily returns 100 times; rank baseline cum_return
    against the shuffled distribution. Pass if baseline > 80th percentile.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field, asdict
from typing import Any

import pandas as pd

from ..engine.loop import run_backtest
from ..runner.ast_checker import assert_safe
from ..runner.progress import ProgressPublisher
from ..runner.result_collector import RunResult
from ..sdk.context import Context

logger = logging.getLogger(__name__)


@dataclass
class GateReport:
    name: str
    passed: bool
    score: int  # 0..100
    note: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class OverfitReport:
    gate1: GateReport
    gate2: GateReport
    gate3: GateReport
    gate4: GateReport
    total_score: int  # 0..100, weighted
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate1": asdict(self.gate1),
            "gate2": asdict(self.gate2),
            "gate3": asdict(self.gate3),
            "gate4": asdict(self.gate4),
            "total_score": self.total_score,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _exec_user_code(code: str, ctx: Context) -> dict[str, Any]:
    """Compile + exec user code into a sandboxed globals dict."""
    from ..runner.worker import _build_user_globals

    g = _build_user_globals()
    compiled = compile(code, "<overfit_strategy>", "exec")
    exec(compiled, g, g)
    return g


def _fresh_ctx(params: dict[str, Any] | None = None) -> Context:
    ctx = Context()
    for k, v in (params or {}).items():
        try:
            ctx.set_param(k, v)
        except Exception:
            pass
    return ctx


def _run_one(
    code: str,
    *,
    start: str | None = None,
    end: str | None = None,
    params: dict[str, Any] | None = None,
    provider: Any | None = None,
    publisher: ProgressPublisher | None = None,
) -> RunResult | None:
    """Run a backtest with date overrides; return None on failure."""
    ctx = _fresh_ctx(params)
    g = _exec_user_code(code, ctx)
    if start:
        ctx.start = start
    if end:
        ctx.end = end
    if provider is None:
        from ..engine.data_provider import QlibProvider

        provider = QlibProvider()
    pub = publisher or ProgressPublisher(run_id="_overfit")
    try:
        return run_backtest(ctx=ctx, provider=provider, user_globals=g, publisher=pub)
    except Exception as e:
        logger.warning("overfit subrun failed: %s", e)
        return None


def _equity_to_returns(equity) -> list[float]:
    rets: list[float] = []
    prev = None
    for p in equity or []:
        v = getattr(p, "value", None) if not isinstance(p, dict) else p.get("value")
        if v is None or prev is None or prev == 0:
            prev = v
            continue
        rets.append(v / prev - 1.0)
        prev = v
    return rets


def _pct_split(start: str, end: str, lo: float, hi: float) -> tuple[str, str]:
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    span = (e - s).days
    a = s + pd.Timedelta(days=int(span * lo))
    b = s + pd.Timedelta(days=int(span * hi))
    return a.strftime("%Y-%m-%d"), b.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------
def gate1_train_test(code: str, *, provider: Any | None = None) -> GateReport:
    """70/30 train/test split."""
    # Probe baseline once to learn start/end
    base = _run_one(code, provider=provider)
    if base is None or not base.equity:
        return GateReport("train_test", False, 0, note="基线回测未产出净值，无法分割训测")

    start = base.equity[0].date
    end = base.equity[-1].date
    train_s, train_e = _pct_split(start, end, 0.0, 0.7)
    test_s, test_e = _pct_split(start, end, 0.7, 1.0)

    train = _run_one(code, start=train_s, end=train_e, provider=provider)
    test = _run_one(code, start=test_s, end=test_e, provider=provider)
    if not train or not test:
        return GateReport(
            "train_test",
            False,
            10,
            note="训练或测试段未跑通，可能区间过短或数据缺失",
            detail={"train_window": [train_s, train_e], "test_window": [test_s, test_e]},
        )

    s_train = train.metrics.sharpe
    s_test = test.metrics.sharpe
    r_test = test.metrics.cum_return

    # Score: how close out-of-sample sharpe is to in-sample
    ratio = s_test / s_train if s_train > 0 else 0
    score = 0
    if r_test > 0 and ratio >= 1.0:
        score = 100
    elif r_test > 0 and ratio >= 0.6:
        score = int(60 + 40 * (ratio - 0.6) / 0.4)
    elif r_test > 0 and ratio >= 0.3:
        score = int(30 + 30 * (ratio - 0.3) / 0.3)
    elif r_test > 0:
        score = 20
    else:
        score = 5
    passed = score >= 60

    note = (
        f"训练 sharpe {s_train:.2f} → 测试 sharpe {s_test:.2f} "
        f"(比 {ratio:.2f})，测试收益 {r_test * 100:.2f}%"
    )
    return GateReport(
        "train_test",
        passed,
        score,
        note=note,
        detail={
            "train": [train_s, train_e],
            "test": [test_s, test_e],
            "train_sharpe": s_train,
            "test_sharpe": s_test,
            "test_cum_return": r_test,
        },
    )


def gate2_walkforward(code: str, *, provider: Any | None = None) -> GateReport:
    """3 rolling test folds."""
    base = _run_one(code, provider=provider)
    if base is None or not base.equity:
        return GateReport("walkforward", False, 0, note="基线回测未产出净值，无法走查")

    start = base.equity[0].date
    end = base.equity[-1].date

    folds = [
        _pct_split(start, end, 0.5, 0.7),
        _pct_split(start, end, 0.7, 0.85),
        _pct_split(start, end, 0.85, 1.0),
    ]
    out_sharpes: list[float] = []
    out_returns: list[float] = []
    for s, e in folds:
        r = _run_one(code, start=s, end=e, provider=provider)
        if r is None:
            out_sharpes.append(0.0)
            out_returns.append(0.0)
            continue
        out_sharpes.append(r.metrics.sharpe)
        out_returns.append(r.metrics.cum_return)

    n_pos = sum(1 for s in out_sharpes if s > 0)
    avg_s = sum(out_sharpes) / max(1, len(out_sharpes))

    if n_pos == 3 and avg_s > 0.5:
        score = 100
    elif n_pos >= 2 and avg_s > 0.0:
        score = int(60 + min(40, avg_s * 80))
    elif n_pos >= 2:
        score = 50
    elif n_pos == 1:
        score = 25
    else:
        score = 5
    passed = score >= 60

    note = f"3 段走查 sharpe={[round(s, 2) for s in out_sharpes]}，{n_pos}/3 段为正"
    return GateReport(
        "walkforward",
        passed,
        score,
        note=note,
        detail={"folds": folds, "sharpes": out_sharpes, "returns": out_returns},
    )


def gate3_param_sense(code: str, *, provider: Any | None = None) -> GateReport:
    """Param sensitivity ±20%."""
    base = _run_one(code, provider=provider)
    if base is None or not base.equity:
        return GateReport("param_sense", False, 0, note="基线回测未产出净值")

    # Re-execute to discover param specs
    ctx_probe = _fresh_ctx()
    try:
        _exec_user_code(code, ctx_probe)
        # Calling setup is not strictly required — params are usually declared in setup
        if "setup" in {k for k in dir(ctx_probe)}:
            pass
        # Actually params are recorded via ctx.param() inside user setup; we must
        # do a "boot-only" run by exec'ing then calling setup().
        if "setup" in _exec_user_code.__globals__ if False else True:
            pass
    except Exception:
        return GateReport("param_sense", False, 30, note="无法探测参数列表")

    # The proper way: do a tiny baseline run (we already did) — its config holds params
    params = base.config.get("params") if isinstance(base.config, dict) else None
    declared: dict[str, list[Any]] = {}
    if isinstance(params, dict):
        for name, spec in params.items():
            choices = (spec or {}).get("choices") or []
            default = (spec or {}).get("default")
            if choices:
                declared[name] = list(choices)
            elif isinstance(default, (int, float)):
                lo = default * 0.8
                hi = default * 1.2
                declared[name] = sorted(set([type(default)(lo), default, type(default)(hi)]))
    if not declared:
        return GateReport(
            "param_sense", True, 75,
            note="未声明 ctx.param()，跳过参敏检测（视为 75 分）",
        )

    base_sharpe = base.metrics.sharpe
    samples: list[float] = [base_sharpe]
    sample_detail: list[dict[str, Any]] = []
    for name, choices in declared.items():
        # Test up to 3 alternative values (skip baseline)
        test_choices = [c for c in choices[:5] if c != base.config.get("params", {}).get(name, {}).get("default")][:3]
        for v in test_choices:
            r = _run_one(code, params={name: v}, provider=provider)
            sh = r.metrics.sharpe if r is not None else 0.0
            samples.append(sh)
            sample_detail.append({"param": name, "value": v, "sharpe": sh})
            if len(sample_detail) >= 6:  # cap total work
                break
        if len(sample_detail) >= 6:
            break

    if not sample_detail:
        return GateReport(
            "param_sense", True, 75, note="参数无可枚举值，参敏跳过（75 分）"
        )

    mean = sum(samples) / len(samples)
    var = sum((s - mean) ** 2 for s in samples) / len(samples)
    std = math.sqrt(var)
    cv = std / abs(mean) if abs(mean) > 1e-9 else 1.0

    if cv < 0.3:
        score = 100
    elif cv < 0.5:
        score = 80
    elif cv < 0.8:
        score = 55
    elif cv < 1.2:
        score = 30
    else:
        score = 10
    passed = score >= 60
    note = f"参数扰动 {len(sample_detail)} 次，sharpe 标准差 {std:.2f}/均值 {mean:.2f}，变异系数 {cv:.2f}"
    return GateReport(
        "param_sense",
        passed,
        score,
        note=note,
        detail={"samples": sample_detail, "baseline_sharpe": base_sharpe, "cv": cv},
    )


def gate4_monte_carlo(code: str, *, provider: Any | None = None, n_sims: int = 100) -> GateReport:
    """Bootstrap shuffle daily returns; rank baseline."""
    base = _run_one(code, provider=provider)
    if base is None or not base.equity:
        return GateReport("monte_carlo", False, 0, note="基线无净值，无法蒙卡")

    rets = _equity_to_returns(base.equity)
    if len(rets) < 30:
        return GateReport(
            "monte_carlo", True, 70,
            note=f"样本仅 {len(rets)} 个交易日，蒙卡跳过（70 分）",
        )

    rng = random.Random(42)
    final_returns: list[float] = []
    for _ in range(n_sims):
        shuffled = rets[:]
        rng.shuffle(shuffled)
        v = 1.0
        peak = 1.0
        for r in shuffled:
            v *= 1.0 + r
            if v > peak:
                peak = v
        final_returns.append(v - 1.0)

    base_ret = base.metrics.cum_return
    rank = sum(1 for r in final_returns if r < base_ret) / len(final_returns)

    if rank >= 0.95:
        score = 100
    elif rank >= 0.80:
        score = int(60 + 40 * (rank - 0.80) / 0.15)
    elif rank >= 0.60:
        score = int(30 + 30 * (rank - 0.60) / 0.20)
    elif rank >= 0.40:
        score = 20
    else:
        score = 5
    passed = score >= 60
    note = (
        f"蒙卡 {n_sims} 次随机洗牌，策略累计收益 {base_ret * 100:.2f}% "
        f"位于第 {rank * 100:.0f} 百分位"
    )
    return GateReport(
        "monte_carlo",
        passed,
        score,
        note=note,
        detail={"baseline_return": base_ret, "rank_pct": rank, "n_sims": n_sims},
    )


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------
def run_overfit_check(
    code: str,
    *,
    provider: Any | None = None,
    skip_ast: bool = False,
) -> OverfitReport:
    """Run all 4 gates sequentially and return a weighted report."""
    if not skip_ast:
        assert_safe(code)

    warnings: list[str] = []

    g1 = _safe_gate("gate1_train_test", lambda: gate1_train_test(code, provider=provider), warnings)
    g2 = _safe_gate("gate2_walkforward", lambda: gate2_walkforward(code, provider=provider), warnings)
    g3 = _safe_gate("gate3_param_sense", lambda: gate3_param_sense(code, provider=provider), warnings)
    g4 = _safe_gate("gate4_monte_carlo", lambda: gate4_monte_carlo(code, provider=provider), warnings)

    total = int(g1.score * 0.30 + g2.score * 0.30 + g3.score * 0.20 + g4.score * 0.20)
    return OverfitReport(g1, g2, g3, g4, total_score=total, warnings=warnings)


def _safe_gate(name: str, fn, warnings: list[str]) -> GateReport:
    try:
        return fn()
    except Exception as e:
        logger.exception("gate %s crashed", name)
        warnings.append(f"{name}: {e}")
        return GateReport(name=name, passed=False, score=0, note=f"关卡运行错误：{e}")


__all__ = ["GateReport", "OverfitReport", "run_overfit_check"]
