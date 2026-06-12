"""Subprocess worker entrypoint.

Run as ``python -m backend.services.engine.strategy_lab.runner.worker``
(or from ``subprocess_runner.py``). Reads a JSON RunRequest from stdin,
runs the backtest, writes the RunResult to Redis under qm:lab:result:{run_id}
and pushes progress events under qm:lab:progress:{run_id}.

The process exits with code 0 on success, 1 on user-script failure, 2 on
infrastructure errors. Stdout/stderr are captured by the parent and merged
into the result logs.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback
from typing import Any

from .ast_checker import ASTCheckError, assert_safe
from .progress import Phase, ProgressPublisher, RunStatus
from .result_collector import RunResult, compute_script_sha, store_result
from ..sdk.context import Context

logger = logging.getLogger(__name__)


def _build_user_globals() -> dict[str, Any]:
    """Sanitize globals dict the user script will exec into."""
    safe_builtins: dict[str, Any] = {
        # Core types
        "abs": abs, "all": all, "any": any, "bool": bool, "bytes": bytes,
        "callable": callable, "chr": chr, "complex": complex, "dict": dict,
        "divmod": divmod, "enumerate": enumerate, "filter": filter, "float": float,
        "frozenset": frozenset, "hex": hex, "int": int, "isinstance": isinstance,
        "issubclass": issubclass, "iter": iter, "len": len, "list": list,
        "map": map, "max": max, "min": min, "next": next, "object": object,
        "oct": oct, "ord": ord, "pow": pow, "print": print, "range": range,
        "repr": repr, "reversed": reversed, "round": round, "set": set,
        "slice": slice, "sorted": sorted, "str": str, "sum": sum, "tuple": tuple,
        "type": type, "zip": zip,
        # Exceptions user code may catch
        "Exception": Exception, "ValueError": ValueError, "KeyError": KeyError,
        "TypeError": TypeError, "RuntimeError": RuntimeError,
        "ZeroDivisionError": ZeroDivisionError, "IndexError": IndexError,
        "True": True, "False": False, "None": None,
        "__name__": "__strategy__",
    }
    return {"__builtins__": safe_builtins}


def run_request(req: dict[str, Any]) -> int:
    run_id: str = req["run_id"]
    code: str = req["code"]
    params: dict[str, Any] = req.get("params") or {}
    qlib_data_path: str | None = req.get("qlib_data_path")

    publisher = ProgressPublisher(run_id=run_id)
    publisher.set_status(RunStatus.running, started_at=time.time())
    publisher.publish(Phase.boot, 1.0, "worker booted")

    started_at = time.time()
    try:
        publisher.publish(Phase.ast_check, 3.0, "AST checking script")
        assert_safe(code)

        # Build provider — InMemory wins if test passed it via the request
        provider = _resolve_provider(req, qlib_data_path)

        ctx = Context()
        for k, v in params.items():
            try:
                ctx.set_param(k, v)
            except Exception:
                pass

        publisher.publish(Phase.setup, 5.0, "executing script body")
        user_globals = _build_user_globals()
        try:
            compiled = compile(code, f"<strategy:{run_id}>", "exec")
            exec(compiled, user_globals, user_globals)
        except Exception as e:
            tb = traceback.format_exc()
            return _fail(run_id, publisher, started_at, code, params, f"script load failed: {e}", tb, ctx=ctx, exit_code=1)

        # Apply params after exec, so any ctx.param() declarations take precedence
        from ..engine.loop import run_backtest

        try:
            result = run_backtest(
                ctx=ctx,
                provider=provider,
                user_globals=user_globals,
                publisher=publisher,
            )
        except Exception as e:
            tb = traceback.format_exc()
            return _fail(run_id, publisher, started_at, code, params, str(e), tb, ctx=ctx, exit_code=1)

        result.run_id = run_id
        result.script_sha = compute_script_sha(code, params)
        result.config = ctx.to_config_dict()
        # Re-attach data_snapshot_at via provider helper if present
        try:
            from ..engine.data_provider import data_snapshot_at
            result.data_snapshot_at = data_snapshot_at(qlib_data_path)
        except Exception:
            pass

        result.logs = list(ctx._logs)
        result.overlays = {
            "lines": list(ctx._plot_lines),
            "markers": list(ctx._plot_markers),
        }
        store_result(result)
        publisher.publish(Phase.done, 100.0, "ok")
        publisher.set_status(
            RunStatus.success,
            finished_at=time.time(),
            elapsed_sec=result.elapsed_sec,
            n_trades=result.metrics.n_trades,
            cum_return=result.metrics.cum_return,
        )
        return 0

    except ASTCheckError as e:
        return _fail(run_id, publisher, started_at, code, params, str(e), "", exit_code=1)
    except Exception as e:
        return _fail(run_id, publisher, started_at, code, params, str(e), traceback.format_exc(), exit_code=2)


def _resolve_provider(req: dict[str, Any], qlib_data_path: str | None) -> Any:
    """Worker uses real Qlib by default; tests patch ``runner.worker._TEST_PROVIDER``."""
    test_provider = globals().get("_TEST_PROVIDER")
    if test_provider is not None:
        return test_provider
    from ..engine.data_provider import QlibProvider
    return QlibProvider(data_path=qlib_data_path)


def _fail(
    run_id: str,
    publisher: ProgressPublisher,
    started_at: float,
    code: str,
    params: dict[str, Any],
    err: str,
    tb: str,
    *,
    ctx: Context | None = None,
    exit_code: int = 1,
) -> int:
    finished_at = time.time()
    result = RunResult(
        run_id=run_id,
        status="failed",
        error=err,
        error_traceback=tb,
        config=ctx.to_config_dict() if ctx is not None else {},
        script_sha=compute_script_sha(code, params),
        elapsed_sec=round(finished_at - started_at, 3),
        started_at=started_at,
        finished_at=finished_at,
    )
    if ctx is not None:
        result.logs = list(ctx._logs)
    store_result(result)
    publisher.publish(Phase.done, 100.0, f"failed: {err[:120]}")
    publisher.set_status(RunStatus.failed, finished_at=finished_at, error=err)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        print("worker: empty stdin, expected JSON RunRequest", file=sys.stderr)
        return 2
    try:
        req = json.loads(raw)
    except Exception as e:
        print(f"worker: bad request JSON: {e}", file=sys.stderr)
        return 2
    return run_request(req)


if __name__ == "__main__":
    sys.exit(main())
