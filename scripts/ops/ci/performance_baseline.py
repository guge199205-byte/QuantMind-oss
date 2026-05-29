#!/usr/bin/env python3
"""
四核心服务进程内性能基准测试。

说明：
1. 使用 FastAPI TestClient，在同一进程内压测关键 HTTP 路由；
2. 结果用于重构后“相对基线”对比，不代表真实网络部署吞吐；
3. 输出 JSON 报告到 tests/reports/。
"""

from __future__ import annotations

import json
import logging
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from fastapi.testclient import TestClient

# 允许在仓库根目录直接运行：python backend/scripts/performance_baseline.py
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass(frozen=True)
class EndpointCase:
    name: str
    method: str
    path: str
    expected_status: tuple[int, ...]
    headers: dict[str, str] | None = None


@dataclass(frozen=True)
class ServiceCase:
    name: str
    app_import: str
    endpoints: tuple[EndpointCase, ...]


CASES: tuple[ServiceCase, ...] = (
    ServiceCase(
        name="quantmind-api",
        app_import="backend.services.api.main:app",
        endpoints=(
            EndpointCase("health", "GET", "/health", (200,)),
            EndpointCase("root", "GET", "/", (200,)),
            EndpointCase(
                "community_posts_list",
                "GET",
                "/api/v1/community/posts?page=1&pageSize=20&sort=latest",
                (200, 400),
                headers={"x-tenant-id": "perf-benchmark"},
            ),
        ),
    ),
    ServiceCase(
        name="quantmind-trade",
        app_import="backend.services.trade.main:app",
        endpoints=(
            EndpointCase("health", "GET", "/health", (200,)),
            EndpointCase("root", "GET", "/", (200,)),
            EndpointCase(
                "simulation_settings",
                "GET",
                "/api/v1/simulation/settings",
                (200, 401, 403),
            ),
        ),
    ),
    ServiceCase(
        name="quantmind-engine",
        app_import="backend.services.engine.main:app",
        endpoints=(
            EndpointCase("health", "GET", "/health", (200,)),
            EndpointCase("root", "GET", "/", (200,)),
            EndpointCase("inference_models", "GET",
                         "/api/v1/inference/models", (200,)),
        ),
    ),
    ServiceCase(
        name="quantmind-stream",
        app_import="backend.services.stream.main:app",
        endpoints=(
            EndpointCase("health", "GET", "/health", (200,)),
            EndpointCase("root", "GET", "/", (200,)),
        ),
    ),
)


def _import_app(import_path: str):
    module_name, app_name = import_path.split(":", 1)
    module = __import__(module_name, fromlist=[app_name])
    return getattr(module, app_name)


def _percentile(samples: list[float], p: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    idx = int((len(ordered) - 1) * p)
    return ordered[idx]


def _benchmark_endpoint(
    client: TestClient,
    case: EndpointCase,
    *,
    warmup: int,
    iterations: int,
) -> dict:
    method = case.method.upper()
    headers = case.headers or {}

    for _ in range(warmup):
        client.request(method, case.path, headers=headers)

    latencies_ms: list[float] = []
    ok = 0
    begin = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter()
        resp = client.request(method, case.path, headers=headers)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)
        if resp.status_code in case.expected_status:
            ok += 1
    elapsed = time.perf_counter() - begin
    throughput = (iterations / elapsed) if elapsed > 0 else 0.0

    return {
        "endpoint": case.path,
        "method": method,
        "iterations": iterations,
        "expected_status": list(case.expected_status),
        "ok": ok,
        "errors": iterations - ok,
        "error_rate": (iterations - ok) / iterations,
        "throughput_rps": throughput,
        "latency_ms": {
            "mean": statistics.mean(latencies_ms),
            "p50": _percentile(latencies_ms, 0.50),
            "p95": _percentile(latencies_ms, 0.95),
            "p99": _percentile(latencies_ms, 0.99),
            "max": max(latencies_ms),
        },
    }


def _iter_summaries(results: Iterable[dict]) -> dict:
    all_rps = [item["throughput_rps"] for item in results]
    all_p95 = [item["latency_ms"]["p95"] for item in results]
    all_err = [item["error_rate"] for item in results]
    return {
        "avg_rps": statistics.mean(all_rps) if all_rps else 0.0,
        "avg_p95_ms": statistics.mean(all_p95) if all_p95 else 0.0,
        "max_p95_ms": max(all_p95) if all_p95 else 0.0,
        "max_error_rate": max(all_err) if all_err else 0.0,
    }


def run_baseline(*, warmup: int = 30, iterations: int = 300) -> dict:
    services: list[dict] = []
    for service_case in CASES:
        app = _import_app(service_case.app_import)
        service_results: list[dict] = []
        with TestClient(app) as client:
            for endpoint_case in service_case.endpoints:
                service_results.append(
                    _benchmark_endpoint(
                        client,
                        endpoint_case,
                        warmup=warmup,
                        iterations=iterations,
                    )
                )
        services.append(
            {
                "service": service_case.name,
                "endpoints": service_results,
                "summary": _iter_summaries(service_results),
            }
        )

    overall_rows = [
        endpoint for svc in services for endpoint in svc["endpoints"]]
    return {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "mode": "in-process-testclient",
            "warmup": warmup,
            "iterations": iterations,
        },
        "services": services,
        "overall": _iter_summaries(overall_rows),
    }


def main() -> int:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    report = run_baseline()
    reports_dir = Path("tests/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = reports_dir / f"performance_baseline_{ts}.json"
    out.write_text(json.dumps(report, ensure_ascii=False,
                   indent=2), encoding="utf-8")

    print(f"Report: {out}")
    print("Overall:")
    print(
        f"  avg_rps={report['overall']['avg_rps']:.2f}, "
        f"avg_p95_ms={report['overall']['avg_p95_ms']:.2f}, "
        f"max_p95_ms={report['overall']['max_p95_ms']:.2f}, "
        f"max_error_rate={report['overall']['max_error_rate']:.4f}"
    )
    for svc in report["services"]:
        s = svc["summary"]
        print(
            f"  - {svc['service']}: avg_rps={s['avg_rps']:.2f}, "
            f"avg_p95_ms={s['avg_p95_ms']:.2f}, max_error_rate={s['max_error_rate']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
