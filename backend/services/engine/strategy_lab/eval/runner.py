"""Eval runner — drives the 30-prompt evaluation through a CodeGenerator.

Two generators ship out of the box:
- `CannedGenerator` — returns hand-curated reference solutions, used by pytest
  to validate the harness itself + scorer + prompts dataset.
- `LiveLLMGenerator` — calls a Qwen/OpenAI-compatible chat completion endpoint
  using the same env-var stack as ai_ide/chat.py.

Use `EvalRunner.run()` to score an entire dataset and `format_markdown_report`
to write a human-readable report.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .prompts import EvalPrompt, PROMPT_DATASET
from .scorer import PromptScore, Scorer

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """你是 QuantMind Strategy Lab 的策略代码生成助手。
请严格按照以下 SDK 规范生成 Python 代码（只返回代码，不要任何解释或 markdown 围栏）：

1. 必须定义 `def setup(ctx):` 并设置至少 ctx.universe / ctx.start / ctx.end / ctx.cash
2. 必须定义 `def on_bar(ctx, bar):` 或 `def on_universe(ctx, date, snapshot):` 至少其一
3. 下单只能用：ctx.buy / ctx.sell / ctx.set_position / ctx.set_target_holdings
4. 风控只能用：ctx.set_stop_loss / ctx.set_take_profit / ctx.set_account_stop_loss / ctx.set_max_holding_days
5. 数据访问只能用：ctx.history / ctx.feature / ctx.snapshot / ctx.benchmark_history
6. 禁止使用：os / sys / subprocess / open / eval / exec / __import__
7. 标准 universe 名：'csi300' / 'csi500' / 'all_a'；单股写 ['sh600519'] 这种 list

只输出代码，不要写 markdown ``` 围栏。"""


# ---------------------------------------------------------------------------
# Code generator interface
# ---------------------------------------------------------------------------

class CodeGenerator(ABC):
    @abstractmethod
    def generate(self, prompt: EvalPrompt) -> str:
        """Return Python source for the given prompt (best-effort)."""

    def close(self) -> None:  # optional cleanup
        return None


class CannedGenerator(CodeGenerator):
    """Returns canned reference solutions — used by pytest to validate the harness."""

    def __init__(self, overrides: dict[str, str] | None = None) -> None:
        self._overrides = overrides or {}

    def generate(self, prompt: EvalPrompt) -> str:
        if prompt.id in self._overrides:
            return self._overrides[prompt.id]
        return _CANNED_SOLUTIONS.get(prompt.id, _CANNED_SOLUTIONS["__fallback__"])


class LiveLLMGenerator(CodeGenerator):
    """Calls Qwen/OpenAI-compatible endpoint synchronously.

    Reads the same env-vars as ai_ide/chat.py — AI_IDE_LLM_BASE_URL,
    AI_IDE_LLM_API_KEY, AI_IDE_LLM_MODEL — with sensible fallbacks.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        import httpx  # local import — avoids cost when only using CannedGenerator

        self._key = (
            api_key
            or os.getenv("AI_IDE_LLM_API_KEY")
            or os.getenv("AI_IDE_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        self._base = (
            base_url
            or os.getenv("AI_IDE_LLM_BASE_URL")
            or os.getenv("AI_IDE_BASE_URL")
            or os.getenv("OPENAI_API_BASE")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self._model = (
            model
            or os.getenv("AI_IDE_LLM_MODEL")
            or os.getenv("AI_IDE_MODEL")
            or "qwen-max"
        )
        if not self._key:
            raise RuntimeError(
                "LiveLLMGenerator requires AI_IDE_LLM_API_KEY or OPENAI_API_KEY in env"
            )
        self._client = httpx.Client(timeout=timeout)

    def generate(self, prompt: EvalPrompt) -> str:
        url = self._base.rstrip("/") + "/chat/completions"
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt.user_prompt},
            ],
            "temperature": 0.1,
        }
        try:
            resp = self._client.post(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {self._key}",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code != 200:
                logger.error("LLM HTTP %d: %s", resp.status_code, resp.text[:300])
                return f"# LLM_ERROR status={resp.status_code}\n"
            payload = resp.json()
            content = (
                payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return _strip_markdown_fence(content)
        except Exception as e:  # noqa: BLE001
            logger.exception("LLM call failed for %s", prompt.id)
            return f"# LLM_EXCEPTION {type(e).__name__}: {e}\n"

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # noqa: BLE001
            pass


def _strip_markdown_fence(text: str) -> str:
    """Strip ```python ... ``` fences if the LLM adds them despite system prompt."""
    text = text.strip()
    if text.startswith("```"):
        # remove leading line (```python or ```)
        lines = text.split("\n")
        if lines:
            lines = lines[1:]
        # remove trailing ```
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text


# ---------------------------------------------------------------------------
# Runner + report
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    total: int
    passed: int
    pass_rate: float
    pass_rate_pct: float
    by_category: dict[str, dict[str, int]]
    scores: list[PromptScore] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "pass_rate": self.pass_rate,
            "pass_rate_pct": self.pass_rate_pct,
            "by_category": self.by_category,
            "scores": [s.to_dict() for s in self.scores],
        }


class EvalRunner:
    def __init__(
        self,
        generator: CodeGenerator,
        scorer: Scorer | None = None,
        dataset: tuple[EvalPrompt, ...] = PROMPT_DATASET,
    ) -> None:
        self._gen = generator
        self._scorer = scorer or Scorer()
        self._dataset = dataset

    def run(self) -> EvalResult:
        scores: list[PromptScore] = []
        for prompt in self._dataset:
            try:
                code = self._gen.generate(prompt)
            except Exception as e:  # noqa: BLE001
                code = f"# GENERATOR_FAILURE: {type(e).__name__}: {e}"
            score = self._scorer.score(prompt, code)
            scores.append(score)

        passed = sum(1 for s in scores if s.passed)
        total = len(scores)
        rate = passed / total if total else 0.0

        by_cat: dict[str, dict[str, int]] = {}
        for s in scores:
            cat = by_cat.setdefault(s.category, {"total": 0, "passed": 0})
            cat["total"] += 1
            if s.passed:
                cat["passed"] += 1

        return EvalResult(
            total=total,
            passed=passed,
            pass_rate=rate,
            pass_rate_pct=round(rate * 100, 2),
            by_category=by_cat,
            scores=scores,
        )

    def close(self) -> None:
        self._gen.close()


def format_markdown_report(result: EvalResult, title: str = "Strategy Lab AI 30-Prompt Eval") -> str:
    lines = [
        f"# {title}",
        "",
        f"- 总数: **{result.total}**",
        f"- 通过: **{result.passed}**",
        f"- 通过率: **{result.pass_rate_pct:.2f}%**",
        f"- 验收门槛: ≥ 60% (Sprint 1 Day 5)",
        "",
        "## 分类统计",
        "",
        "| 类别 | 通过 / 总计 | 通过率 |",
        "|---|---|---|",
    ]
    for cat, stats in sorted(result.by_category.items()):
        rate = stats["passed"] / stats["total"] if stats["total"] else 0.0
        lines.append(f"| {cat} | {stats['passed']} / {stats['total']} | {rate * 100:.1f}% |")
    lines += [
        "",
        "## 单题明细",
        "",
        "| ID | 类别 | C1 AST | C2 setup | C3 hook | C4 markers | 通过 | 失败原因 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in result.scores:
        marks = lambda b: "✓" if b else "✗"  # noqa: E731
        reasons = "; ".join(s.failure_reasons)[:120] if s.failure_reasons else "—"
        lines.append(
            f"| {s.prompt_id} | {s.category} "
            f"| {marks(s.ast_safe)} | {marks(s.has_setup)} "
            f"| {marks(s.has_hook)} | {marks(s.must_contain_ok)} "
            f"| {'**PASS**' if s.passed else 'FAIL'} | {reasons} |"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Canned reference solutions for offline harness verification
# ---------------------------------------------------------------------------

_CANNED_SOLUTIONS: dict[str, str] = {
    "p01": """
def setup(ctx):
    ctx.universe = ['sh600519']
    ctx.start = '2024-01-02'
    ctx.end = '2024-06-30'
    ctx.cash = 1_000_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=60, field='close')
    if len(closes) < 60:
        return
    ma20 = closes.tail(20).mean()  # MA20
    ma60 = closes.mean()           # MA60
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and ma20 > ma60:
        ctx.buy(bar.symbol, weight=0.5, reason='MA20>MA60')
    elif pos.qty > 0 and ma20 < ma60:
        ctx.sell(bar.symbol, all=True, reason='MA20<MA60')
""",
    "p06": """
def setup(ctx):
    ctx.universe = ['sh600036']
    ctx.start = '2024-01-02'
    ctx.end = '2024-06-30'
    ctx.cash = 500_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=15, field='close')
    if len(closes) < 15:
        return
    diff = closes.diff().dropna()
    gain = diff.clip(lower=0).mean()
    loss = (-diff.clip(upper=0)).mean()
    rs = gain / loss if loss > 0 else 100
    rsi = 100 - 100 / (1 + rs)  # RSI(14)
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and rsi < 30:
        ctx.buy(bar.symbol, weight=0.5, reason='RSI_oversold')
    elif pos.qty > 0 and rsi > 70:
        ctx.sell(bar.symbol, all=True, reason='RSI_overbought')
""",
    "p12": """
def setup(ctx):
    ctx.universe = ['sh600519']
    ctx.start = '2024-01-02'
    ctx.end = '2024-06-30'
    ctx.cash = 1_000_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=22, field='close')
    if len(closes) < 22:
        return
    high22 = float(closes.max())
    s1 = high22 * 0.786
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and abs(bar.close - s1) / s1 < 0.03:
        ctx.buy(bar.symbol, weight=0.5, reason='fib_S1')
        ctx.set_stop_loss(bar.symbol, -0.10)
        ctx.set_take_profit(bar.symbol, 0.15)
""",
    "p15": """
import pandas as pd

def setup(ctx):
    ctx.universe = 'csi300'
    ctx.start = '2024-01-02'
    ctx.end = '2024-06-30'
    ctx.cash = 1_000_000
    ctx.max_positions = 5

def on_universe(ctx, date, snapshot):
    if pd.Timestamp(date).day > 5:
        return
    history = ctx.history(symbols=ctx.universe, n=20, field='close')
    if history.empty:
        return
    rets = history.iloc[-1] / history.iloc[0] - 1
    top = rets.dropna().sort_values(ascending=False).head(5).index.tolist()
    ctx.set_target_holdings(top, reason='top5_momentum')
""",
    "p23": """
def setup(ctx):
    ctx.universe = ['sh600519']
    ctx.start = '2024-01-02'
    ctx.end = '2024-06-30'
    ctx.cash = 500_000

def on_bar(ctx, bar):
    pos = ctx.position(bar.symbol)
    if pos.qty == 0:
        ctx.buy(bar.symbol, weight=0.5, reason='entry')
        ctx.set_stop_loss(bar.symbol, -0.08)
        ctx.set_take_profit(bar.symbol, 0.15)
""",
    "p24": """
def setup(ctx):
    ctx.universe = ['sh600519']
    ctx.start = '2024-01-02'
    ctx.end = '2024-06-30'
    ctx.cash = 1_000_000
    ctx.set_account_stop_loss = -0.20  # noqa

def on_bar(ctx, bar):
    ctx.set_account_stop_loss(-0.20)
    pos = ctx.position(bar.symbol)
    if pos.qty == 0:
        ctx.buy(bar.symbol, weight=0.5, reason='entry')
""",
    "p25": """
def setup(ctx):
    ctx.universe = ['sh600519']
    ctx.start = '2024-01-02'
    ctx.end = '2024-06-30'
    ctx.cash = 1_000_000

def on_bar(ctx, bar):
    pos = ctx.position(bar.symbol)
    if pos.qty == 0:
        ctx.buy(bar.symbol, weight=0.5, reason='entry')
        ctx.set_max_holding_days(bar.symbol, 30)
""",
}

# Default fallback used when no specific canned answer exists — covers
# generic on_bar trend prompts so the dataset is fully covered without
# 30 hand-curated solutions. The harness still validates that each
# prompt's must_contain markers appear, so generic templates fail
# prompts requiring specific markers (intentional).
_GENERIC_ON_BAR = """
def setup(ctx):
    ctx.universe = ['sh600519']
    ctx.start = '2024-01-02'
    ctx.end = '2024-06-30'
    ctx.cash = 1_000_000

def on_bar(ctx, bar):
    closes = ctx.history(symbol=bar.symbol, n=20, field='close')
    if len(closes) < 20:
        return
    ma = closes.mean()
    pos = ctx.position(bar.symbol)
    if pos.qty == 0 and bar.close > ma:
        ctx.buy(bar.symbol, weight=0.5, reason='above_ma')
    elif pos.qty > 0 and bar.close < ma:
        ctx.sell(bar.symbol, all=True, reason='below_ma')
"""

_GENERIC_CROSS_SECTION = """
import pandas as pd

def setup(ctx):
    ctx.universe = 'csi300'
    ctx.start = '2024-01-02'
    ctx.end = '2024-06-30'
    ctx.cash = 1_000_000
    ctx.max_positions = 10

def on_universe(ctx, date, snapshot):
    if pd.Timestamp(date).day > 5:
        return
    history = ctx.history(symbols=ctx.universe, n=20, field='close')
    if history.empty:
        return
    rets = history.iloc[-1] / history.iloc[0] - 1
    top = rets.dropna().sort_values(ascending=False).head(10).index.tolist()
    ctx.set_target_holdings(top, reason='top10')
"""

# Fill in remaining IDs with category-appropriate templates so the dataset
# is fully covered for harness self-test.
for _p in PROMPT_DATASET:
    if _p.id in _CANNED_SOLUTIONS:
        continue
    if _p.category in {"cross_section", "factor"}:
        _CANNED_SOLUTIONS[_p.id] = _GENERIC_CROSS_SECTION
    else:
        _CANNED_SOLUTIONS[_p.id] = _GENERIC_ON_BAR

_CANNED_SOLUTIONS["__fallback__"] = _GENERIC_ON_BAR
