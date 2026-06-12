"""Deterministic 4-criterion scorer for AI-generated Strategy Lab code.

A submission `passes` if and only if all four criteria pass. Each criterion
is independently reported so we can tell *why* a prompt failed:

  C1 ast_safe          — runs through the SDK AST checker without errors
  C2 has_setup         — defines `def setup(ctx):` and sets ctx.start/end/cash/universe
  C3 has_hook          — defines at least one of `on_bar` / `on_universe`
  C4 must_contain      — every prompt-specific marker substring appears in the code

The scorer is deliberately *generous* on must_contain (case-insensitive substring
match) so the gate measures structural correctness, not stylistic mimicry.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, asdict
from typing import Any

from backend.services.engine.strategy_lab.runner.ast_checker import (
    check_source,
)
from .prompts import EvalPrompt


@dataclass
class PromptScore:
    prompt_id: str
    category: str
    ast_safe: bool
    has_setup: bool
    has_hook: bool
    must_contain_ok: bool
    passed: bool
    failure_reasons: list[str]
    code_excerpt: str  # first 200 chars

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Scorer:
    """Stateless scorer — call ``score(prompt, code)``."""

    @staticmethod
    def _run_ast_check(code: str) -> tuple[bool, str]:
        try:
            issues = check_source(code, require_hooks=False)
        except Exception as e:  # noqa: BLE001
            return False, f"ast_checker raised: {type(e).__name__}: {e}"
        if issues:
            head = issues[0]
            return False, f"ast issues ({len(issues)}): {head.code}: {head.message}"
        return True, ""

    @staticmethod
    def _check_setup(code: str) -> tuple[bool, list[str]]:
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, [f"syntax: {e}"]
        setup_fn = next(
            (n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name == "setup"),
            None,
        )
        if setup_fn is None:
            return False, ["missing setup() function"]
        # Walk the setup body looking for ctx.<attr> = ... assignments
        attrs_seen: set[str] = set()
        for node in ast.walk(setup_fn):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if (
                        isinstance(tgt, ast.Attribute)
                        and isinstance(tgt.value, ast.Name)
                        and tgt.value.id == "ctx"
                    ):
                        attrs_seen.add(tgt.attr)
        missing = [a for a in ("universe", "start", "end", "cash") if a not in attrs_seen]
        if missing:
            return False, [f"setup missing ctx.{a}" for a in missing]
        return True, []

    @staticmethod
    def _check_hook(code: str) -> bool:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and n.name in {"on_bar", "on_universe"}:
                return True
        return False

    @staticmethod
    def _check_markers(code: str, markers: tuple[str, ...]) -> tuple[bool, list[str]]:
        if not markers:
            return True, []
        lower = code.lower()
        missing = [m for m in markers if m.lower() not in lower]
        return (not missing), [f"missing marker: {m}" for m in missing]

    def score(self, prompt: EvalPrompt, code: str) -> PromptScore:
        ast_ok, ast_msg = self._run_ast_check(code)
        setup_ok, setup_msgs = self._check_setup(code)
        hook_ok = self._check_hook(code)
        markers_ok, marker_msgs = self._check_markers(code, prompt.must_contain)

        reasons: list[str] = []
        if not ast_ok:
            reasons.append(ast_msg)
        if not setup_ok:
            reasons.extend(setup_msgs)
        if not hook_ok:
            reasons.append("missing on_bar/on_universe")
        if not markers_ok:
            reasons.extend(marker_msgs)

        passed = ast_ok and setup_ok and hook_ok and markers_ok
        excerpt = code.strip()[:200].replace("\n", " ")
        return PromptScore(
            prompt_id=prompt.id,
            category=prompt.category,
            ast_safe=ast_ok,
            has_setup=setup_ok,
            has_hook=hook_ok,
            must_contain_ok=markers_ok,
            passed=passed,
            failure_reasons=reasons,
            code_excerpt=excerpt,
        )
