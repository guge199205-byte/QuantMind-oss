#!/usr/bin/env python3
"""CLI for the Strategy Lab 30-prompt AI eval gate.

Usage:
    # Offline harness self-test (canned generator, fast)
    python scripts/strategy_lab_eval.py

    # Live LLM run (requires AI_IDE_LLM_API_KEY in env)
    python scripts/strategy_lab_eval.py --live

    # Write report to a file (default: stdout)
    python scripts/strategy_lab_eval.py --live --report reports/strategy_lab_eval.md

    # Override pass threshold (default 0.60)
    python scripts/strategy_lab_eval.py --live --threshold 0.7

Exit code 0 = passed gate, 1 = below threshold, 2 = setup/runtime error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make ``backend`` importable when run from repo root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.strategy_lab.eval import (  # noqa: E402
    CannedGenerator,
    EvalRunner,
    LiveLLMGenerator,
)
from backend.services.engine.strategy_lab.eval.runner import (  # noqa: E402
    format_markdown_report,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Strategy Lab AI prompt eval harness")
    p.add_argument("--live", action="store_true",
                   help="Use real LLM (Qwen/OpenAI-compatible) instead of canned solutions")
    p.add_argument("--threshold", type=float, default=0.60,
                   help="Pass-rate threshold (default 0.60 per Sprint 1 Day 5)")
    p.add_argument("--report", type=str, default="",
                   help="Path to write markdown report (default stdout)")
    p.add_argument("--json", type=str, default="",
                   help="Optional JSON dump of full result")
    p.add_argument("--model", type=str, default="",
                   help="Override LLM model (e.g. qwen-plus)")
    args = p.parse_args()

    try:
        if args.live:
            print(f"[eval] using LIVE LLM (model={args.model or os.getenv('AI_IDE_LLM_MODEL', 'qwen-max')})",
                  file=sys.stderr)
            gen = LiveLLMGenerator(model=args.model or None)
        else:
            print("[eval] using canned generator (offline harness self-test)", file=sys.stderr)
            gen = CannedGenerator()
    except Exception as e:
        print(f"[eval] generator setup failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    try:
        runner = EvalRunner(generator=gen)
        result = runner.run()
    finally:
        try:
            gen.close()
        except Exception:
            pass

    md = format_markdown_report(result)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(md, encoding="utf-8")
        print(f"[eval] markdown report → {args.report}", file=sys.stderr)
    else:
        sys.stdout.write(md)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"[eval] json result → {args.json}", file=sys.stderr)

    print(
        f"[eval] result: {result.passed}/{result.total} passed "
        f"({result.pass_rate_pct:.2f}%); threshold={args.threshold * 100:.0f}%",
        file=sys.stderr,
    )

    if result.pass_rate < args.threshold:
        print("[eval] FAILED — below threshold", file=sys.stderr)
        return 1
    print("[eval] PASSED", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
