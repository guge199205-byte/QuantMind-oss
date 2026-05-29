import sys
from pathlib import Path

import pytest

# 添加项目路径（兼容直接执行 pytest）
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))

from backend.services.engine.ai_strategy.services.llm_resilience import (  # noqa: E402
    LLMRateLimitError,
    ResilientLLMRouter,
)


class _FailProvider:
    def generate_code(self, prompt: str, mode: str = "simple"):
        raise RuntimeError("provider failed")


class _OkProvider:
    def __init__(self, label: str):
        self.label = label

    def generate_code(self, prompt: str, mode: str = "simple"):
        return f"code_from_{self.label}", {"mode": mode}


def test_failover_from_primary_to_fallback():
    router = ResilientLLMRouter(
        provider_factories={
            "qwen": _FailProvider,
            "deepseek": lambda: _OkProvider("deepseek"),
        },
        max_retries=1,
        retry_base_seconds=0.0,
        failure_threshold=1,
        circuit_open_seconds=60.0,
        rate_limit_rpm=100,
        max_concurrency=1,
    )

    code, meta = router.generate_code("p", preferred="qwen", mode="complex")
    assert code == "code_from_deepseek"
    assert meta.get("provider") == "deepseek"


def test_circuit_breaker_open_skips_failed_provider():
    router = ResilientLLMRouter(
        provider_factories={
            "qwen": _FailProvider,
            "deepseek": lambda: _OkProvider("deepseek"),
        },
        max_retries=1,
        retry_base_seconds=0.0,
        failure_threshold=1,
        circuit_open_seconds=120.0,
        rate_limit_rpm=100,
        max_concurrency=1,
    )

    # 第一次调用触发 qwen 熔断并回退到 deepseek
    code1, meta1 = router.generate_code("p1", preferred="qwen")
    assert code1 == "code_from_deepseek"
    assert meta1.get("provider") == "deepseek"

    # 第二次调用应直接跳过已熔断的 qwen，继续走 deepseek
    code2, meta2 = router.generate_code("p2", preferred="qwen")
    assert code2 == "code_from_deepseek"
    assert meta2.get("provider") == "deepseek"


def test_rate_limit_enforced():
    router = ResilientLLMRouter(
        provider_factories={"qwen": lambda: _OkProvider("qwen")},
        max_retries=1,
        retry_base_seconds=0.0,
        failure_threshold=3,
        circuit_open_seconds=30.0,
        rate_limit_rpm=1,
        max_concurrency=1,
    )

    router.generate_code("first", preferred="qwen")
    with pytest.raises(LLMRateLimitError):
        router.generate_code("second", preferred="qwen")
