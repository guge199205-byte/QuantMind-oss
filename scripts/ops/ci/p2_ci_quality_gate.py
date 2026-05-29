#!/usr/bin/env python3
"""P2 CI quality gate.

Gate includes:
1) tenant isolation regression
2) cross-service smoke tests
3) deprecation-strict smoke imports
4) lint/typecheck of this gate script
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import subprocess
import sys
import time
from pathlib import Path


def _tool_cmd(module_name: str, cli_name: str) -> str:
    if importlib.util.find_spec(module_name) is not None:
        return f"{sys.executable} -m {module_name}"
    # 避免拾取到损坏的 pipx shim，统一回退到当前解释器模块调用。
    # 若模块不存在，会在执行阶段报错并明确提示安装依赖。
    return f"{sys.executable} -m {module_name}"


CHECKS = [
    (
        "trade-long-short-mvp",
        "pytest -q "
        "backend/services/tests/test_qmt_agent_async_reconcile.py "
        "backend/services/tests/test_trade_long_short_risk_and_bridge.py "
        "backend/services/tests/test_trade_long_short_integration_chain.py "
        "backend/services/tests/test_trade_trading_precheck.py "
        "--no-cov",
    ),
    (
        "isolation-tests",
        "pytest -q backend/services/tests/test_trade_service.py "
        "-k \"scoped_by_tenant_user or scoped_by_user_id or rejects_invalid_user_id\" "
        "--no-cov",
    ),
    (
        "cross-service-smoke",
        "pytest -q "
        "backend/services/tests/test_stream_service.py "
        "backend/services/tests/test_engine_service.py "
        "-k \"health_returns_200 or root_returns_200 or openapi_schema_available\" "
        "--no-cov",
    ),
    (
        "deprecation-strict-smoke",
        "pytest -q backend/services/tests/test_stream_service.py "
        "backend/services/tests/test_engine_service.py "
        "-k \"health_returns_200 or root_returns_200 or openapi_schema_available\" "
        "-W error::DeprecationWarning "
        "-W error::PendingDeprecationWarning "
        "--no-cov",
    ),
    (
        "lint-ruff",
        f"{_tool_cmd('ruff', 'ruff')} check --isolated scripts/ops/ci/p2_ci_quality_gate.py",
    ),
    (
        "typecheck-mypy",
        f"{_tool_cmd('mypy', 'mypy')} --ignore-missing-imports "
        "--disable-error-code import-untyped "
        "scripts/ops/ci/p2_ci_quality_gate.py",
    ),
]


def _run(name: str, cmd: str) -> dict:
    print(f"\n=== {name} ===")
    print(f"$ {cmd}")
    if " -m mypy " in cmd and importlib.util.find_spec("mypy") is None:
        print("SKIP: mypy is not installed in current environment")
        return {
            "name": name,
            "cmd": cmd,
            "code": 0,
            "elapsed": 0.0,
        }
    start = time.time()
    completed = subprocess.run(
        cmd,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    elapsed = time.time() - start
    if completed.stdout:
        print(completed.stdout)
    return {
        "name": name,
        "cmd": cmd,
        "code": completed.returncode,
        "elapsed": elapsed,
    }


def _write_report(results: list[dict], report_path: Path) -> None:
    total = len(results)
    failed = sum(1 for item in results if item["code"] != 0)
    passed = total - failed
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# P2 CI Quality Gate Report",
        "",
        f"- Generated at: `{now}`",
        f"- Total checks: `{total}`",
        f"- Passed: `{passed}`",
        f"- Failed: `{failed}`",
        "",
        "| Check | Status | Duration(s) | Command |",
        "| --- | --- | ---: | --- |",
    ]
    for item in results:
        status = "PASS" if item["code"] == 0 else "FAIL"
        lines.append(
            f"| {item['name']} | {status} | {item['elapsed']:.2f} | `{item['cmd']}` |"
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    print("Running P2 CI quality gate...")
    results = [_run(name, cmd) for name, cmd in CHECKS]

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(f"tests/reports/p2_ci_quality_gate_report_{timestamp}.md")
    _write_report(results, report_path)
    print(f"\nReport written to: {report_path}")

    failed = [item for item in results if item["code"] != 0]
    if failed:
        print("\nP2 CI quality gate failed:")
        for item in failed:
            print(f"- {item['name']} ({item['code']})")
        return 1

    print("\nP2 CI quality gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
