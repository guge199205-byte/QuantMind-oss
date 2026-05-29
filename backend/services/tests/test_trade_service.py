"""
test_trade_service.py - quantmind-trade 服务测试
验证交易核心服务的健康检查、路由注册和基本功能
"""

import pytest
from fastapi import HTTPException, status
from starlette.requests import Request
from datetime import datetime, timezone

# ============================================================
# 1. App 创建与基础路由测试
# ============================================================


class TestTradeAppCreation:
    """测试 quantmind-trade 应用对象的创建和基础配置"""

    def test_app_instance_exists(self):
        """验证 FastAPI 应用对象可以被导入"""
        from backend.services.trade.main import app

        assert app is not None
        assert app.title == "QuantMind Trade Core"
        assert app.version == "2.0.0"

    def test_health_endpoint_registered(self):
        """验证 /health 端点已注册"""
        from backend.services.trade.main import app

        routes = [r.path for r in app.routes]
        assert "/health" in routes

    def test_root_endpoint_registered(self):
        """验证 / 端点已注册"""
        from backend.services.trade.main import app

        routes = [r.path for r in app.routes]
        assert "/" in routes

    def test_cors_middleware_configured(self):
        """验证 CORS 中间件已配置"""
        from backend.services.trade.main import app

        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes


class TestTradeRouterRegistration:
    """测试所有交易路由模块是否正确注册"""

    def _get_route_paths(self):
        from backend.services.trade.main import app

        return [r.path for r in app.routes if hasattr(r, "path")]

    def test_orders_routes_registered(self):
        """验证订单路由已注册"""
        paths = self._get_route_paths()
        order_paths = [p for p in paths if "/api/v1/orders" in p]
        assert len(order_paths) > 0, f"未找到订单路由，当前路由: {paths}"

    def test_trades_history_routes_registered(self):
        """验证成交记录路由已注册"""
        paths = self._get_route_paths()
        trade_paths = [p for p in paths if "/api/v1/trades" in p]
        assert len(trade_paths) > 0, f"未找到成交记录路由，当前路由: {paths}"

    def test_portfolio_routes_registered(self):
        """验证投资组合路由已注册"""
        paths = self._get_route_paths()
        portfolio_paths = [p for p in paths if "/api/v1/portfolios" in p]
        assert len(portfolio_paths) > 0, f"未找到投资组合路由，当前路由: {paths}"

    def test_simulation_routes_registered(self):
        """验证模拟盘路由已注册"""
        paths = self._get_route_paths()
        sim_paths = [p for p in paths if "/api/v1/simulation" in p]
        assert len(sim_paths) > 0, f"未找到模拟盘路由，当前路由: {paths}"

    def test_real_trading_routes_registered(self):
        """验证实盘交易路由已注册"""
        paths = self._get_route_paths()
        real_paths = [p for p in paths if "/api/v1/real-trading" in p]
        assert len(real_paths) > 0, f"未找到实盘交易路由，当前路由: {paths}"


# ============================================================
# 2. HTTP 接口测试
# ============================================================


class TestTradeHealthEndpoints:
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

        from backend.services.trade import main as trade_main

        original_lifespan = trade_main.app.router.lifespan_context
        trade_main.app.router.lifespan_context = mock_lifespan
        self.client = TestClient(trade_main.app)
        yield
        trade_main.app.router.lifespan_context = original_lifespan

    def test_health_returns_200(self):
        """验证 /health 返回 200"""
        response = self.client.get("/health")
        assert response.status_code == 200

    def test_health_response_body(self):
        """验证 /health 返回正确的服务标识"""
        response = self.client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "quantmind-trade"

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
        assert "QuantMind Trade Core V2" in data["message"]

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
        assert schema["info"]["title"] == "QuantMind Trade Core"

    def test_openapi_has_trade_paths(self):
        """验证 OpenAPI schema 包含交易相关路径"""
        response = self.client.get("/openapi.json")
        schema = response.json()
        paths = list(schema.get("paths", {}).keys())
        assert any("/orders" in p for p in paths), f"未找到订单路径: {paths}"
        assert any("/portfolios" in p for p in paths), f"未找到组合路径: {paths}"
        assert any("/simulation" in p for p in paths), f"未找到模拟路径: {paths}"

    def test_metrics_endpoint_exposes_service_health_gauge(self):
        """验证 /metrics 暴露统一服务健康指标"""
        self.client.get("/health")
        response = self.client.get("/metrics")
        assert response.status_code == 200
        body = response.text
        assert "quantmind_service_health_status" in body
        assert 'service="quantmind-trade"' in body

    def test_protected_endpoint_requires_auth(self):
        """验证受保护的交易端点需要认证"""
        response = self.client.get("/api/v1/orders")
        # 应返回 401 或 403（取决于中间件实现）
        assert response.status_code in [
            401,
            403,
            422,
        ], f"受保护端点应需要认证，实际返回: {response.status_code}"

    def test_real_trading_endpoint_requires_auth(self):
        """验证 real_trading 端点需要认证"""
        response = self.client.get("/api/v1/real-trading/status")
        assert response.status_code in [
            401,
            403,
            422,
        ], f"real_trading 端点应需要认证，实际返回: {response.status_code}"


# ============================================================
# 3. 依赖注入测试
# ============================================================


class TestTradeDependencies:
    """测试交易服务的依赖注入模块"""

    def test_auth_context_dataclass(self):
        """验证 AuthContext 数据类结构"""
        from backend.services.trade.deps import AuthContext

        ctx = AuthContext(user_id="u123", tenant_id="t1", raw_sub="u123", roles=[])
        assert ctx.user_id == "u123"
        assert ctx.tenant_id == "t1"


class TestTradeTenantIsolation:
    """验证订单/成交单条读取时的租户隔离"""

    @pytest.mark.asyncio
    async def test_get_order_scoped_by_tenant_user_returns_404_when_not_found(self, monkeypatch):
        from uuid import uuid4

        from backend.services.trade.deps import AuthContext
        from backend.services.trade.routers import trading_orders
        from backend.services.trade.services.order_service import OrderService

        captured = {}

        async def fake_get_order(self, order_id, tenant_id=None, user_id=None):
            captured["order_id"] = order_id
            captured["tenant_id"] = tenant_id
            captured["user_id"] = user_id
            return None

        monkeypatch.setattr(OrderService, "get_order", fake_get_order)

        order_id = uuid4()
        auth = AuthContext(user_id=1001, tenant_id="tenant-a", raw_sub="1001", roles=[])

        with pytest.raises(HTTPException) as exc:
            await trading_orders.get_order(
                order_id=order_id,
                auth=auth,
                db=object(),
                redis=object(),
            )

        assert exc.value.status_code == status.HTTP_404_NOT_FOUND
        assert captured["order_id"] == order_id
        assert captured["tenant_id"] == "tenant-a"
        assert captured["user_id"] == 1001

    @pytest.mark.asyncio
    async def test_get_trade_scoped_by_tenant_user_returns_404_when_not_found(self, monkeypatch):
        from uuid import uuid4

        from backend.services.trade.deps import AuthContext
        from backend.services.trade.routers import trading_history
        from backend.services.trade.services.trade_service import TradeService

        captured = {}

        async def fake_get_trade(self, trade_id, tenant_id=None, user_id=None):
            captured["trade_id"] = trade_id
            captured["tenant_id"] = tenant_id
            captured["user_id"] = user_id
            return None

        monkeypatch.setattr(TradeService, "get_trade", fake_get_trade)

        trade_id = uuid4()
        auth = AuthContext(user_id=2002, tenant_id="tenant-b", raw_sub="2002", roles=[])

        with pytest.raises(HTTPException) as exc:
            await trading_history.get_trade(
                trade_id=trade_id,
                auth=auth,
                db=object(),
                redis=object(),
            )

        assert exc.value.status_code == status.HTTP_404_NOT_FOUND
        assert captured["trade_id"] == trade_id
        assert captured["tenant_id"] == "tenant-b"
        assert captured["user_id"] == 2002

    @pytest.mark.asyncio
    async def test_orders_get_rejects_invalid_user_id_in_token(self):
        from uuid import uuid4

        from backend.services.trade.deps import AuthContext
        from backend.services.trade.routers import trading_orders

        auth = AuthContext(user_id="invalid-user", tenant_id="tenant-a", raw_sub="invalid-user", roles=[])

        with pytest.raises(HTTPException) as exc:
            await trading_orders.get_order(
                order_id=uuid4(),
                auth=auth,
                db=object(),
                redis=object(),
            )

        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_trades_get_rejects_invalid_user_id_in_token(self):
        from uuid import uuid4

        from backend.services.trade.deps import AuthContext
        from backend.services.trade.routers import trading_history

        auth = AuthContext(user_id="invalid-user", tenant_id="tenant-b", raw_sub="invalid-user", roles=[])

        with pytest.raises(HTTPException) as exc:
            await trading_history.get_trade(
                trade_id=uuid4(),
                auth=auth,
                db=object(),
                redis=object(),
            )

        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_portfolio_calculate_scoped_by_user_id(self, monkeypatch):
        from backend.services.trade.routers import portfolios

        captured = {}

        async def fake_get_portfolio(db, portfolio_id, user_id=None, tenant_id=None):
            captured["portfolio_id"] = portfolio_id
            captured["user_id"] = user_id
            captured["tenant_id"] = tenant_id
            return None

        monkeypatch.setattr(portfolios.PortfolioService, "get_portfolio", fake_get_portfolio)

        with pytest.raises(HTTPException) as exc:
            await portfolios.calculate_portfolio_metrics(
                request=self._fake_request("/api/v1/portfolios/11/calculate"),
                portfolio_id=11,
                tenant_id="tenant-x",
                user_id=3001,
                db=object(),
            )

        assert exc.value.status_code == status.HTTP_404_NOT_FOUND
        assert captured["portfolio_id"] == 11
        assert captured["user_id"] == 3001
        assert captured["tenant_id"] == "tenant-x"

    @pytest.mark.asyncio
    async def test_trading_orders_list_orders_forwards_date_range(self, monkeypatch):
        from backend.services.trade.deps import AuthContext
        from backend.services.trade.routers import trading_orders
        from backend.services.trade.services.order_service import OrderService

        captured = {}

        async def fake_list_orders(self, query):
            captured["tenant_id"] = query.tenant_id
            captured["user_id"] = query.user_id
            captured["start_date"] = query.start_date
            captured["end_date"] = query.end_date
            captured["limit"] = query.limit
            captured["offset"] = query.offset
            return []

        monkeypatch.setattr(OrderService, "list_orders", fake_list_orders)

        auth = AuthContext(user_id=1001, tenant_id="tenant-a", raw_sub="1001", roles=[])
        start_date = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 3, 19, 23, 59, 59, tzinfo=timezone.utc)

        await trading_orders.list_orders(
            portfolio_id=11,
            symbol="AAPL",
            status="filled",
            trading_mode="REAL",
            start_date=start_date,
            end_date=end_date,
            limit=20,
            offset=10,
            auth=auth,
            db=object(),
            redis=object(),
        )

        assert captured["tenant_id"] == "tenant-a"
        assert captured["user_id"] == 1001
        assert captured["start_date"] == start_date
        assert captured["end_date"] == end_date
        assert captured["limit"] == 20
        assert captured["offset"] == 10

    @pytest.mark.asyncio
    async def test_simulation_orders_list_orders_forwards_date_range(self, monkeypatch):
        from backend.services.trade.deps import AuthContext
        from backend.services.trade.routers import simulation_orders
        from backend.services.trade.simulation.services.order_service import SimOrderService

        captured = {}

        async def fake_list_orders(
            self,
            tenant_id,
            user_id,
            *,
            portfolio_id=None,
            status=None,
            symbol=None,
            start_date=None,
            end_date=None,
            limit=50,
            offset=0,
        ):
            captured["tenant_id"] = tenant_id
            captured["user_id"] = user_id
            captured["portfolio_id"] = portfolio_id
            captured["status"] = status
            captured["symbol"] = symbol
            captured["start_date"] = start_date
            captured["end_date"] = end_date
            captured["limit"] = limit
            captured["offset"] = offset
            return []

        monkeypatch.setattr(SimOrderService, "list_orders", fake_list_orders)

        auth = AuthContext(user_id=2002, tenant_id="tenant-b", raw_sub="2002", roles=[])
        start_date = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 3, 19, 23, 59, 59, tzinfo=timezone.utc)

        await simulation_orders.list_orders(
            portfolio_id=22,
            status="filled",
            symbol="600519.SH",
            start_date=start_date,
            end_date=end_date,
            limit=30,
            offset=5,
            auth=auth,
            db=object(),
        )

        assert captured["tenant_id"] == "tenant-b"
        assert captured["user_id"] == 2002
        assert captured["portfolio_id"] == 22
        assert captured["status"] == "filled"
        assert captured["symbol"] == "600519.SH"
        assert captured["start_date"] == start_date
        assert captured["end_date"] == end_date
        assert captured["limit"] == 30
        assert captured["offset"] == 5

    @pytest.mark.asyncio
    async def test_position_get_scoped_by_user_id(self, monkeypatch):
        from backend.services.trade.routers import positions

        captured = {}

        async def fake_get_position(db, position_id, user_id=None, tenant_id=None):
            captured["position_id"] = position_id
            captured["user_id"] = user_id
            captured["tenant_id"] = tenant_id
            return None

        monkeypatch.setattr(positions.PositionService, "get_position", fake_get_position)

        with pytest.raises(HTTPException) as exc:
            await positions.get_position(
                request=self._fake_request("/api/v1/portfolios/1/positions/21"),
                position_id=21,
                tenant_id="tenant-x",
                user_id=4001,
                db=object(),
            )

        assert exc.value.status_code == status.HTTP_404_NOT_FOUND
        assert captured["position_id"] == 21
        assert captured["user_id"] == 4001
        assert captured["tenant_id"] == "tenant-x"

    @pytest.mark.asyncio
    async def test_position_price_update_scoped_by_user_id(self, monkeypatch):
        from decimal import Decimal

        from backend.services.trade.routers import positions

        captured = {}

        async def fake_update_position_price(db, position_id, current_price, user_id=None, tenant_id=None):
            captured["position_id"] = position_id
            captured["user_id"] = user_id
            captured["tenant_id"] = tenant_id
            raise ValueError("持仓不存在")

        monkeypatch.setattr(
            positions.PositionService,
            "update_position_price",
            fake_update_position_price,
        )

        with pytest.raises(HTTPException) as exc:
            await positions.update_position_price(
                request=self._fake_request("/api/v1/positions/31/price"),
                position_id=31,
                current_price=Decimal("10.5"),
                tenant_id="tenant-x",
                user_id=5001,
                db=object(),
            )

        assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
        assert captured["position_id"] == 31
        assert captured["user_id"] == 5001
        assert captured["tenant_id"] == "tenant-x"

    @pytest.mark.asyncio
    async def test_trades_list_accepts_lowercase_trading_mode(self, monkeypatch):
        from backend.services.trade.deps import AuthContext
        from backend.services.trade.models.order import TradingMode
        from backend.services.trade.routers import trading_history
        from backend.services.trade.services.trade_service import TradeService

        captured = {}

        async def fake_list_trades(self, query):
            captured["trading_mode"] = query.trading_mode
            return []

        monkeypatch.setattr(TradeService, "list_trades", fake_list_trades)

        auth = AuthContext(user_id=1001, tenant_id="tenant-a", raw_sub="1001", roles=[])
        await trading_history.list_trades(
            trading_mode="real",
            auth=auth,
            db=object(),
            redis=object(),
        )
        assert captured["trading_mode"] == TradingMode.REAL

    @pytest.mark.asyncio
    async def test_trades_list_rejects_invalid_trading_mode(self):
        from backend.services.trade.deps import AuthContext
        from backend.services.trade.routers import trading_history

        auth = AuthContext(user_id=1001, tenant_id="tenant-a", raw_sub="1001", roles=[])
        with pytest.raises(HTTPException) as exc:
            await trading_history.list_trades(
                trading_mode="invalid_mode",
                auth=auth,
                db=object(),
                redis=object(),
            )
        assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @staticmethod
    def _fake_request(path: str = "/") -> Request:
        return Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": b"",
                "headers": [],
                "client": ("127.0.0.1", 12345),
                "server": ("testserver", 80),
            }
        )
