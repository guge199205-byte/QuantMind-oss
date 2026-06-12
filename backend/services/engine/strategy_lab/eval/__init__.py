"""Strategy Lab AI prompt evaluation harness.

Sprint 1 Day 5 acceptance gate: 30 standard prompts, ≥60% pass rate.

This package provides:
- `prompts.py` — the 30-prompt dataset
- `scorer.py` — deterministic 4-criterion scorer
- `runner.py` — sync runner + markdown report writer

The runner accepts a pluggable `CodeGenerator` so pytest can run the harness
offline against a canned generator while CLI invocations with `--live` can
hit the real Qwen/OpenAI-compatible LLM.
"""

from .prompts import EvalPrompt, PROMPT_DATASET
from .scorer import PromptScore, Scorer
from .runner import (
    CodeGenerator,
    CannedGenerator,
    LiveLLMGenerator,
    EvalRunner,
)

__all__ = [
    "EvalPrompt",
    "PROMPT_DATASET",
    "PromptScore",
    "Scorer",
    "CodeGenerator",
    "CannedGenerator",
    "LiveLLMGenerator",
    "EvalRunner",
]
