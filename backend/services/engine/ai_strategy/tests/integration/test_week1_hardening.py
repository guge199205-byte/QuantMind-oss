import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.services.engine.ai_strategy.app_factory import create_app
from backend.services.engine.ai_strategy.services.cos_uploader import InvalidUserIdError

# 添加项目路径（兼容直接执行 pytest）
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def mock_startup_health_dependencies(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")

    monkeypatch.setattr(
        "backend.services.engine.ai_strategy.provider_registry.get_provider",
        lambda: object(),
    )

    async def _noop():
        return None

    monkeypatch.setattr(
        "backend.services.engine.ai_strategy.services.selection.vector_parser.get_strategy_vector_parser",
        _noop,
    )
    monkeypatch.setattr(
        "backend.services.engine.ai_strategy.services.selection.schema_retriever.get_schema_retriever",
        _noop,
    )


def test_query_pool_auth_status_contract():
    client = TestClient(create_app())

    no_ctx = client.post(
        "/api/v1/strategy/query-pool",
        json={"dsl": "SELECT symbol WHERE pe <= 20"},
    )
    assert no_ctx.status_code == 401
    assert "未认证" in no_ctx.json().get("detail", "")

    user_only = client.post(
        "/api/v1/strategy/query-pool",
        headers={"X-User-Id": "1"},
        json={"dsl": "SELECT symbol WHERE pe <= 20"},
    )
    assert user_only.status_code == 403
    assert "未授权" in user_only.json().get("detail", "")


def test_legacy_routes_disabled_by_default():
    client = TestClient(create_app())
    resp = client.post(
        "/api/v1/legacy/strategy/save-pool-file",
        json={"user_id": "1", "pool_name": "p", "pool": [{"symbol": "000001.SZ"}]},
    )

    assert resp.status_code == 200
    body = resp.json()
    # shared.response.error 返回业务错误码
    assert body.get("code") == 2001
    assert "legacy 路由已关闭" in body.get("message", "")


def test_save_to_cloud_invalid_user_id_returns_422(monkeypatch):
    class _DummyStorage:
        async def save(self, user_id, name, code, metadata):
            raise InvalidUserIdError(f"user_id 必须为整数类型字符串，当前值: {user_id}")

    monkeypatch.setattr(
        "backend.shared.strategy_storage.get_strategy_storage_service",
        lambda: _DummyStorage(),
    )

    client = TestClient(create_app())
    resp = client.post(
        "/api/v1/strategy/save-to-cloud",
        headers={"X-User-Id": "abc"},
        json={
            "user_id": "abc",
            "strategy_name": "s1",
            "code": "print(1)",
            "metadata": {},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "user_id 必须为整数类型字符串" in body["error"]


def test_health_endpoint_exposes_startup_status():
    with TestClient(create_app()) as client:
        resp = client.get("/api/v1/health")

    assert resp.status_code == 200
    body = resp.json()
    startup_health = body["data"]["startup_health"]
    assert startup_health["ready"] is True
    assert startup_health["vector_parser_ready"] is True
    assert startup_health["schema_retriever_ready"] is True
