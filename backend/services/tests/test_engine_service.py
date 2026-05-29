"""
test_engine_service.py - quantmind-engine 服务测试
验证计算引擎服务的健康检查、路由注册和基本功能
"""

from pathlib import Path

import pytest

# ============================================================
# 1. App 创建与基础路由测试
# ============================================================


class TestEngineAppCreation:
    """测试 quantmind-engine 应用对象的创建和基础配置"""

    def test_app_instance_exists(self):
        """验证 FastAPI 应用对象可以被导入"""
        from backend.services.engine.main import app

        assert app is not None
        assert app.title == "QuantMind Computational Engine"
        assert app.version == "2.0.0"

    def test_health_endpoint_registered(self):
        """验证 /health 端点已注册"""
        from backend.services.engine.main import app

        routes = [r.path for r in app.routes]
        assert "/health" in routes

    def test_root_endpoint_registered(self):
        """验证 / 端点已注册"""
        from backend.services.engine.main import app

        routes = [r.path for r in app.routes]
        assert "/" in routes

    def test_cors_middleware_configured(self):
        """验证 CORS 中间件已配置"""
        from backend.services.engine.main import app

        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes


class TestEngineRouterRegistration:
    """测试计算引擎路由模块注册情况"""

    def _get_route_paths(self):
        from backend.services.engine.main import app

        return [r.path for r in app.routes if hasattr(r, "path")]

    def test_inference_routes_registered(self):
        """验证推理路由已注册（唯一的独立实现模块）"""
        paths = self._get_route_paths()
        inference_paths = [p for p in paths if "/api/v1/inference" in p]
        assert len(inference_paths) > 0, f"未找到推理路由，当前路由: {paths}"

    def test_pipeline_routes_registered(self):
        """验证闭环编排路由已注册"""
        paths = self._get_route_paths()
        pipeline_paths = [p for p in paths if "/api/v1/pipeline" in p]
        assert len(pipeline_paths) > 0, f"未找到 pipeline 路由，当前路由: {paths}"


# ============================================================
# 1.5 配置一致性测试
# ============================================================


class TestEngineConfigConsistency:
    """测试 engine 配置来源一致性"""

    def test_engine_env_should_not_define_database_url(self):
        """
        DATABASE_URL 统一以项目根目录 .env 为准。
        backend/services/engine/.env 不应再定义重复 DATABASE_URL。
        """
        engine_env = Path("backend/services/engine/.env")
        if not engine_env.exists():
            pytest.skip("engine .env 文件不存在，跳过一致性检查")

        content = engine_env.read_text(encoding="utf-8")
        has_database_url = any(
            line.strip().startswith("DATABASE_URL=")
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
        assert not has_database_url, "backend/services/engine/.env 存在重复 DATABASE_URL，请统一使用根目录 .env"

    def test_engine_env_should_not_define_redis_connection(self):
        """
        REDIS_HOST/REDIS_PORT/REDIS_PASSWORD 统一以项目根目录 .env 为准。
        backend/services/engine/.env 不应再定义重复 Redis 连接配置。
        """
        engine_env = Path("backend/services/engine/.env")
        if not engine_env.exists():
            pytest.skip("engine .env 文件不存在，跳过一致性检查")

        content = engine_env.read_text(encoding="utf-8")
        forbidden_keys = ("REDIS_HOST=", "REDIS_PORT=", "REDIS_PASSWORD=")
        has_redis_keys = any(
            any(line.strip().startswith(key) for key in forbidden_keys)
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
        assert not has_redis_keys, "backend/services/engine/.env 存在重复 Redis 连接配置，请统一使用根目录 .env"

    def test_engine_env_should_not_define_qlib_provider_config(self):
        """
        QLIB_PROVIDER_URI/QLIB_REGION 统一以项目根目录 .env 为准。
        backend/services/engine/.env 不应再定义重复 Qlib Provider 配置。
        """
        engine_env = Path("backend/services/engine/.env")
        if not engine_env.exists():
            pytest.skip("engine .env 文件不存在，跳过一致性检查")

        content = engine_env.read_text(encoding="utf-8")
        forbidden_keys = ("QLIB_PROVIDER_URI=", "QLIB_REGION=")
        has_qlib_provider_keys = any(
            any(line.strip().startswith(key) for key in forbidden_keys)
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
        assert (
            not has_qlib_provider_keys
        ), "backend/services/engine/.env 存在重复 Qlib Provider 配置，请统一使用根目录 .env"

    def test_model_qlib_class_declaration_should_match_model_file(self):
        """
        model_qlib 的 workflow/metadata 声明应与 model.pkl 实际类型一致。
        """
        model_dir = Path("models/production/model_qlib")
        model_path = model_dir / "model.pkl"
        workflow_path = model_dir / "workflow_config.yaml"
        metadata_path = model_dir / "metadata.json"

        if not (model_path.exists() and workflow_path.exists() and metadata_path.exists()):
            pytest.skip("model_qlib 产物不完整，跳过一致性检查")

        import json
        import pickle

        import yaml

        try:
            with model_path.open("rb") as f:
                model = pickle.load(f)
        except ModuleNotFoundError as exc:
            pytest.skip(f"依赖缺失，跳过模型一致性检查: {exc}")

        with workflow_path.open("r", encoding="utf-8") as f:
            workflow = yaml.safe_load(f) or {}
        with metadata_path.open("r", encoding="utf-8") as f:
            metadata = json.load(f) or {}

        task_model = (workflow.get("task") or {}).get("model") or {}
        declared_workflow_cls = f"{task_model.get('module_path')}.{task_model.get('class')}"
        declared_metadata_cls = metadata.get("resolved_class")
        actual_cls = f"{type(model).__module__}.{type(model).__name__}"

        assert declared_workflow_cls == actual_cls
        assert declared_metadata_cls == actual_cls


# ============================================================
# 2. HTTP 接口测试
# ============================================================


class TestEngineHealthEndpoints:
    """测试健康检查等无需认证的端点"""

    @property
    def _internal_headers(self):
        from backend.shared.auth import get_internal_call_secret

        return {"X-Internal-Call": get_internal_call_secret()}

    @pytest.fixture(autouse=True)
    def setup_client(self):
        """设置测试客户端，mock 掉 lifespan 中的外部依赖"""
        from contextlib import asynccontextmanager

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        @asynccontextmanager
        async def mock_lifespan(app: FastAPI):
            yield

        from backend.services.engine import main as engine_main

        original_lifespan = engine_main.app.router.lifespan_context
        engine_main.app.router.lifespan_context = mock_lifespan
        self.client = TestClient(engine_main.app)
        yield
        engine_main.app.router.lifespan_context = original_lifespan

    def test_health_returns_200(self):
        """验证 /health 返回 200"""
        response = self.client.get("/health")
        assert response.status_code == 200

    def test_health_response_body(self):
        """验证 /health 返回正确的服务标识"""
        response = self.client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "quantmind-engine"

    def test_health_response_contains_request_id(self):
        """验证响应头包含 X-Request-ID"""
        response = self.client.get("/health")
        assert response.headers.get("X-Request-ID")

    def test_root_returns_200(self):
        """验证 / 返回 200"""
        response = self.client.get("/")
        assert response.status_code == 200

    def test_root_response_body(self):
        """验证 / 返回正确消息"""
        response = self.client.get("/")
        data = response.json()
        assert "QuantMind Engine Core V2" in data["message"]

    def test_nonexistent_route_returns_404(self):
        """验证不存在的路由返回 404"""
        response = self.client.get(
            "/api/v1/nonexistent_endpoint_xyz",
            headers=self._internal_headers,
        )
        assert response.status_code == 404

    def test_nonexistent_route_error_contract(self):
        """验证 404 响应符合统一错误契约"""
        response = self.client.get(
            "/api/v1/nonexistent_endpoint_xyz",
            headers=self._internal_headers,
        )
        body = response.json()
        assert body["error"]["code"] == "HTTP_404"
        assert body["error"]["request_id"]

    def test_api_v1_requires_internal_secret(self):
        """验证 /api/v1/* 业务路由缺失内部密钥时返回 401"""
        response = self.client.get("/api/v1/nonexistent_endpoint_xyz")
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid internal authentication"

    def test_openapi_schema_available(self):
        """验证 OpenAPI 文档可访问"""
        response = self.client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "QuantMind Computational Engine"

    def test_metrics_endpoint_exposes_service_health_gauge(self):
        """验证 /metrics 暴露统一服务健康指标"""
        self.client.get("/health")
        response = self.client.get("/metrics")
        assert response.status_code == 200
        body = response.text
        assert "quantmind_service_health_status" in body
        assert 'service="quantmind-engine"' in body
