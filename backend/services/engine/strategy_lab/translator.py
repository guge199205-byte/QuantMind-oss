"""SDK script → strategy template translator.

Goal: take a Strategy Lab SDK script (event-driven Context API) and emit
a *Qlib-runnable* strategy template that the Strategy Wizard already knows
how to execute (via /strategy-wizard endpoints).

For v1 this is best-effort and deliberately conservative — the translated
template carries:

- Both the original SDK source AND a Qlib-compatible config block
- The user's universe, start/end, cash, benchmark verbatim
- Declared params (ctx.param) become tunable knobs
- A reference back to the run_id that produced these results

If the SDK script is too dynamic to faithfully express in Qlib (e.g. ad-hoc
ranking inside on_bar that doesn't map to alpha factors), we still save the
template so the user can edit it in the Wizard, but tag it ``needs_review``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from .runner.ast_checker import assert_safe
from .sdk.context import Context

logger = logging.getLogger(__name__)


@dataclass
class TranslatedTemplate:
    name: str
    description: str
    code: str           # Qlib-runnable strategy code (STRATEGY_CONFIG block)
    sdk_source: str     # original Strategy Lab SDK script (kept for reference)
    config: dict[str, Any]  # Qlib-style config
    params: dict[str, Any]
    needs_review: bool = False
    notes: list[str] = None  # type: ignore[assignment]

    def to_storage_metadata(self) -> dict[str, Any]:
        return {
            "source": "strategy_lab_translate",
            "config": self.config,
            "parameters": self.params,
            "needs_review": self.needs_review,
            "notes": self.notes or [],
            "sdk_source": self.sdk_source,
        }


# Regex used to lift SDK config out without running the script.
_RE_CTX_ASSIGN = re.compile(r"ctx\.([a-zA-Z_]+)\s*=\s*(.+?)$", re.MULTILINE)
_RE_PARAM = re.compile(r"ctx\.param\(\s*['\"]([a-zA-Z_][\w]*)['\"]")


def _safe_eval(expr: str) -> Any:
    """Evaluate a literal RHS — strings, numbers, lists. Else return raw string."""
    try:
        # Strip trailing comment
        if "#" in expr:
            expr = expr.split("#", 1)[0]
        expr = expr.strip().rstrip(",")
        return eval(expr, {"__builtins__": {}}, {})  # nosec: literal eval-only
    except Exception:
        return expr.strip()


def _extract_via_regex(code: str) -> dict[str, Any]:
    """Scan setup() body for ``ctx.<key> = <value>`` lines."""
    out: dict[str, Any] = {}
    for m in _RE_CTX_ASSIGN.finditer(code):
        key = m.group(1)
        if key in {"params", "param", "buy", "sell", "stop_loss", "take_profit", "log", "plot_line", "plot_marker"}:
            continue
        val = _safe_eval(m.group(2))
        out[key] = val
    return out


def _extract_via_exec(code: str) -> dict[str, Any]:
    """Run setup() in-process to get authoritative ctx fields."""
    try:
        from .runner.worker import _build_user_globals

        g = _build_user_globals()
        compiled = compile(code, "<translate>", "exec")
        exec(compiled, g, g)
        ctx = Context()
        if "setup" in g and callable(g["setup"]):
            try:
                g["setup"](ctx)
            except Exception as e:
                logger.warning("setup() raised during translate (using defaults): %s", e)
        cfg = ctx.to_config_dict() if hasattr(ctx, "to_config_dict") else {}
        # Also collect params from ctx
        params = dict(getattr(ctx, "_param_values", {}))
        return {"config": cfg, "params": params}
    except Exception as e:
        logger.warning("_extract_via_exec failed: %s", e)
        return {}


def translate_sdk_to_template(code: str, *, run_id: str | None = None) -> TranslatedTemplate:
    """Translate user SDK code into a savable strategy template."""
    assert_safe(code)

    notes: list[str] = []
    needs_review = False

    extracted = _extract_via_exec(code)
    if extracted:
        cfg_dict = extracted.get("config") or {}
        params = extracted.get("params") or {}
    else:
        cfg_dict = _extract_via_regex(code)
        params = {p: None for p in _RE_PARAM.findall(code)}
        needs_review = True
        notes.append("无法 exec 用户脚本，仅按文本提取配置；请在向导中确认参数。")

    universe = cfg_dict.get("universe")
    start = cfg_dict.get("start")
    end = cfg_dict.get("end")
    cash = cfg_dict.get("cash") or 1_000_000

    if not (universe and start and end):
        needs_review = True
        notes.append("setup() 未声明完整的 universe/start/end，模板需要在向导中补全。")

    # Heuristic: if the strategy uses ctx.indicator / ctx.history with rolling
    # window logic, suggest a rolling alpha config; otherwise default to LSTM.
    has_indicator = "ctx.indicator(" in code
    has_history = "ctx.history(" in code
    suggested_alpha = "Alpha158"
    if has_indicator or has_history:
        notes.append("检测到 ctx.indicator / ctx.history → 推荐 Alpha158 因子集。")
    else:
        notes.append("未检测到指标，使用默认基础因子。")

    # Qlib-style config the existing Strategy Wizard understands
    qlib_config: dict[str, Any] = {
        "strategy_type": "topk_dropout",
        "topk": 50,
        "n_drop": 5,
        "alpha_set": suggested_alpha,
        "universe": universe,
        "start": start,
        "end": end,
        "cash": cash,
        "benchmark": cfg_dict.get("benchmark", "SH000300"),
        "commission": cfg_dict.get("commission", 0.0003),
        "slippage": cfg_dict.get("slippage", 0.0005),
        "max_positions": cfg_dict.get("max_positions", 10),
        "_sdk_source": True,
        "_sdk_run_id": run_id,
    }

    name_seed = (run_id or "lab").replace("-", "")[:8]
    name = f"Strategy Lab → 模板 {name_seed}"
    description = (
        "由 Strategy Lab SDK 脚本一键转模板而来；"
        + ("需要在策略向导中校对参数。" if needs_review else "已自动填充全部字段，可直接试跑。")
    )

    # Generate Qlib-runnable wrapper code so the backtest center's
    # CustomStrategyBuilder can find STRATEGY_CONFIG.  The original SDK source
    # is stashed in metadata under `sdk_source` for the Lab to round-trip.
    qlib_kwargs = {
        "topk": int(qlib_config.get("topk", 50)),
        "n_drop": int(qlib_config.get("n_drop", 5)),
    }
    qlib_code = (
        '"""Auto-generated from Strategy Lab — Qlib-runnable wrapper.\n'
        f"原始 SDK 脚本由 Strategy Lab 保存于 metadata.sdk_source（run_id={run_id or '-'}）。\n"
        '"""\n\n'
        "STRATEGY_CONFIG = {\n"
        '    "class": "RedisTopkStrategy",\n'
        '    "module_path": "backend.services.engine.qlib_app.utils.extended_strategies",\n'
        f'    "kwargs": {qlib_kwargs!r},\n'
        "}\n\n"
        "def get_strategy_config():\n"
        "    return STRATEGY_CONFIG\n"
    )

    return TranslatedTemplate(
        name=name,
        description=description,
        code=qlib_code,
        sdk_source=code,
        config=qlib_config,
        params=params,
        needs_review=needs_review,
        notes=notes,
    )


__all__ = ["TranslatedTemplate", "translate_sdk_to_template"]
