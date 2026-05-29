"""
test_api_service.py - quantmind-api 服务测试
验证业务单体服务的健康检查、路由注册和基本功能
"""

import httpx
import pytest

# ============================================================
# 1. App 创建与基础路由测试 (不依赖外部服务)
# ============================================================


class TestAPIAppCreation:
    """测试 quantmind-api 应用对象的创建和基础配置"""

    def test_app_instance_exists(self):
        """验证 FastAPI 应用对象可以被导入"""
        from backend.services.api.main import app

        assert app is not None
        assert app.title == "QuantMind Consolidated API"
        assert app.version == "2.0.0"

    def test_health_endpoint_registered(self):
        """验证 /health 端点已注册"""
        from backend.services.api.main import app

        routes = [r.path for r in app.routes]
        assert "/health" in routes

    def test_root_endpoint_registered(self):
        """验证 / 端点已注册"""
        from backend.services.api.main import app

        routes = [r.path for r in app.routes]
        assert "/" in routes

    def test_cors_middleware_configured(self):
        """验证 CORS 中间件已配置"""
        from backend.services.api.main import app

        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes


class TestAPIRouterRegistration:
    """测试所有路由模块是否正确注册"""

    def _get_route_paths(self):
        from backend.services.api.main import app

        return [r.path for r in app.routes if hasattr(r, "path")]

    def test_auth_routes_registered(self):
        """验证认证路由已注册"""
        paths = self._get_route_paths()
        auth_paths = [p for p in paths if "/api/v1/" in p and ("login" in p or "register" in p or "auth" in p)]
        assert len(auth_paths) > 0, f"未找到认证路由，当前路由: {paths}"

    def test_user_routes_registered(self):
        """验证用户管理路由已注册"""
        paths = self._get_route_paths()
        user_paths = [p for p in paths if "/api/v1/users" in p]
        assert len(user_paths) > 0, f"未找到用户路由，当前路由: {paths}"

    def test_profile_routes_registered(self):
        """验证用户档案路由已注册"""
        paths = self._get_route_paths()
        profile_paths = [p for p in paths if "/api/v1/profiles" in p]
        assert len(profile_paths) > 0, f"未找到档案路由，当前路由: {paths}"

    def test_community_routes_registered(self):
        """验证社区路由已注册"""
        paths = self._get_route_paths()
        community_paths = [p for p in paths if "/api/v1/community" in p]
        assert len(community_paths) > 0, f"未找到社区路由，当前路由: {paths}"


# ============================================================
# 2. HTTP 接口测试 (使用 TestClient, mock 掉外部依赖)
# ============================================================


class TestAPIHealthEndpoints:
    """测试健康检查等无需认证的端点"""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        """设置测试客户端，mock 掉 lifespan 中的外部依赖"""
        from contextlib import asynccontextmanager

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        @asynccontextmanager
        async def mock_lifespan(app: FastAPI):
            yield

        from backend.services.api import main as api_main

        original_lifespan = api_main.app.router.lifespan_context
        api_main.app.router.lifespan_context = mock_lifespan
        self.client = TestClient(api_main.app)
        yield
        api_main.app.router.lifespan_context = original_lifespan

    def test_health_returns_200(self):
        """验证 /health 返回 200"""
        response = self.client.get("/health")
        assert response.status_code == 200

    def test_health_response_body(self):
        """验证 /health 返回正确的服务标识"""
        response = self.client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "quantmind-api"

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
        assert "QuantMind API Service V2" in data["message"]

    def test_nonexistent_route_returns_404(self):
        """验证不存在的路由返回 404"""
        response = self.client.get("/api/v1/nonexistent_endpoint_xyz")
        assert response.status_code == 404

    def test_nonexistent_route_error_contract(self):
        """验证 404 响应符合统一错误契约"""
        response = self.client.get("/api/v1/nonexistent_endpoint_xyz")
        body = response.json()
        assert body["error"]["code"] == "HTTP_404"
        assert body["error"]["request_id"]

    def test_openapi_schema_available(self):
        """验证 OpenAPI 文档可访问"""
        response = self.client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "QuantMind Consolidated API"
        assert schema["info"]["version"] == "2.0.0"

    def test_openapi_schema_has_tags(self):
        """验证 OpenAPI schema 包含所有注册的标签"""
        response = self.client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})
        assert len(paths) > 5, f"路由数量过少({len(paths)})，可能路由注册不完整"

    def test_metrics_endpoint_exposes_service_health_gauge(self):
        """验证 /metrics 暴露统一服务健康指标"""
        self.client.get("/health")
        response = self.client.get("/metrics")
        assert response.status_code == 200
        body = response.text
        assert "quantmind_service_health_status" in body
        assert 'service="quantmind-api"' in body

    def test_proxy_routes_hidden_from_openapi(self):
        """验证网关代理路由不暴露在 OpenAPI 中"""
        response = self.client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})
        assert "/api/v1/files/{subpath}" not in paths
        assert "/api/v1/execute/{subpath}" not in paths
        assert "/api/v1/ai/{subpath}" not in paths
        assert "/api/v1/config/{subpath}" not in paths
        assert "/api/v1/strategies/{path}" not in paths
        assert "/api/v1/qlib/{path}" not in paths
        assert "/api/v1/simulation/{path}" not in paths


class TestAPIProxyErrorContract:
    """验证代理上游异常映射与错误契约"""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from contextlib import asynccontextmanager

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        @asynccontextmanager
        async def mock_lifespan(app: FastAPI):
            yield

        from backend.services.api import main as api_main

        original_lifespan = api_main.app.router.lifespan_context
        api_main.app.router.lifespan_context = mock_lifespan
        self.client = TestClient(api_main.app)
        yield
        api_main.app.router.lifespan_context = original_lifespan

    def test_engine_proxy_connect_error_maps_to_503(self, monkeypatch):
        async def _raise_connect_error(self, *args, **kwargs):
            raise httpx.ConnectError("connect failed")

        monkeypatch.setattr(httpx.AsyncClient, "request", _raise_connect_error)

        response = self.client.get("/api/v1/strategies")
        body = response.json()
        assert response.status_code == 503
        assert body["error"]["code"] == "HTTP_503"
        assert body["detail"]["service"] == "engine"
        assert body["detail"]["reason"] == "connect_error"
