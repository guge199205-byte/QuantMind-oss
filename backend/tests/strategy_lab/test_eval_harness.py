"""Pytest harness for the 30-prompt AI evaluation gate.

This file runs the eval on a CannedGenerator that returns hand-curated reference
solutions, and asserts:
  1. Dataset has exactly 30 prompts
  2. Scorer correctly identifies passes and failures
  3. The canned reference solutions achieve ≥ 60% pass rate (sanity check the
     harness — if our own canned solutions can't pass 60%, the harness is wrong)

The live LLM run is opt-in via `--strategy-lab-live` flag (skipped here).
"""

from __future__ import annotations

import pytest

from backend.services.engine.strategy_lab.eval import (
    CannedGenerator,
    EvalRunner,
    PROMPT_DATASET,
    Scorer,
)
from backend.services.engine.strategy_lab.eval.runner import format_markdown_report


def test_dataset_has_30_prompts():
    assert len(PROMPT_DATASET) == 30
    ids = [p.id for p in PROMPT_DATASET]
    assert len(set(ids)) == 30, "duplicate prompt ids"


def test_scorer_passes_valid_solution():
    code = """
def setup(ctx):
    ctx.universe = ['sh600519']
    ctx.start = '2024-01-02'
    ctx.end = '2024-06-30'
    ctx.cash = 1_000_000

def on_bar(ctx, bar):
    ctx.buy(bar.symbol, weight=0.5, reason='entry')
"""
    s = Scorer().score(PROMPT_DATASET[0], code)
    assert s.ast_safe
    assert s.has_setup
    assert s.has_hook


def test_scorer_rejects_missing_setup():
    code = """
def on_bar(ctx, bar):
    ctx.buy(bar.symbol, weight=0.5)
"""
    s = Scorer().score(PROMPT_DATASET[0], code)
    assert not s.has_setup
    assert not s.passed


def test_scorer_rejects_missing_hooks():
    code = """
def setup(ctx):
    ctx.universe = ['sh600519']
    ctx.start = '2024-01-02'
    ctx.end = '2024-06-30'
    ctx.cash = 1_000_000
"""
    s = Scorer().score(PROMPT_DATASET[0], code)
    assert not s.has_hook
    assert not s.passed


def test_scorer_rejects_unsafe_imports():
    code = """
import os
def setup(ctx):
    ctx.universe = ['sh600519']
    ctx.start = '2024-01-02'
    ctx.end = '2024-06-30'
    ctx.cash = 1_000_000
def on_bar(ctx, bar):
    pass
"""
    s = Scorer().score(PROMPT_DATASET[0], code)
    assert not s.ast_safe
    assert not s.passed


def test_canned_generator_meets_60pct_gate():
    """The harness's own canned reference solutions must hit ≥ 60% — if not,
    either the canned solutions are broken or the scorer is too strict."""
    runner = EvalRunner(generator=CannedGenerator())
    result = runner.run()
    assert result.total == 30
    assert result.pass_rate >= 0.60, (
        f"Canned solutions pass rate {result.pass_rate_pct:.1f}% < 60% — "
        f"failing prompts: "
        f"{[s.prompt_id + ':' + ';'.join(s.failure_reasons) for s in result.scores if not s.passed]}"
    )


def test_markdown_report_renders_all_rows():
    runner = EvalRunner(generator=CannedGenerator())
    result = runner.run()
    md = format_markdown_report(result)
    assert "Strategy Lab AI 30-Prompt Eval" in md
    for s in result.scores:
        assert s.prompt_id in md, f"missing {s.prompt_id} in report"


@pytest.mark.skip(reason="opt-in live LLM run; invoke via scripts/strategy_lab_eval.py")
def test_live_llm_60pct_gate():
    pass
