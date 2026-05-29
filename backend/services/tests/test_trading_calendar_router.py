from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from datetime import date

from backend.services.api.user_app.middleware.auth import get_current_user


@pytest.fixture
def client():
    from backend.services.api.main import app

    with patch("backend.services.api.main.lifespan", MagicMock()):
        with TestClient(app) as test_client:
            yield test_client


def _mock_user():
    return {"user_id": "u1", "tenant_id": "t1", "is_admin": False}


def test_is_trading_day_route(client):
    from backend.services.api.main import app

    app.dependency_overrides[get_current_user] = _mock_user
    with patch(
        "backend.services.api.routers.trading_calendar.calendar_service.is_trading_day",
        AsyncMock(return_value=True),
    ):
        try:
            response = client.get("/api/v1/market-calendar/is-trading-day?market=SSE&date=2026-04-07")
            assert response.status_code == 200
            payload = response.json()
            assert payload["is_trading_day"] is True
            assert payload["tenant_id"] == "t1"
            assert payload["user_id"] == "u1"
        finally:
            app.dependency_overrides.clear()


def test_next_and_prev_trading_day_routes(client):
    from backend.services.api.main import app

    app.dependency_overrides[get_current_user] = _mock_user
    with patch(
        "backend.services.api.routers.trading_calendar.calendar_service.next_trading_day",
        AsyncMock(return_value=date(2026, 4, 8)),
    ):
        with patch(
            "backend.services.api.routers.trading_calendar.calendar_service.prev_trading_day",
            AsyncMock(return_value=date(2026, 4, 3)),
        ):
            try:
                next_resp = client.get("/api/v1/market-calendar/next-trading-day?market=SSE&date=2026-04-07")
                assert next_resp.status_code == 200
                assert next_resp.json()["next_trading_day"] == "2026-04-08"

                prev_resp = client.get("/api/v1/market-calendar/prev-trading-day?market=SSE&date=2026-04-07")
                assert prev_resp.status_code == 200
                assert prev_resp.json()["prev_trading_day"] == "2026-04-03"
            finally:
                app.dependency_overrides.clear()


def test_batch_check_route(client):
    from backend.services.api.main import app

    app.dependency_overrides[get_current_user] = _mock_user
    mock_result = [
        {"date": "2026-04-07", "is_trading_day": True},
        {"date": "2026-04-08", "is_trading_day": True},
    ]
    with patch(
        "backend.services.api.routers.trading_calendar.calendar_service.batch_is_trading_day",
        AsyncMock(return_value=mock_result),
    ):
        try:
            response = client.post(
                "/api/v1/market-calendar/batch-check",
                json={"market": "SSE", "dates": ["2026-04-07", "2026-04-08"]},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["total"] == 2
            assert payload["results"] == mock_result
        finally:
            app.dependency_overrides.clear()
