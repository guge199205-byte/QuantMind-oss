import httpx

from backend.services.api.routers.proxy_error_mapping import map_upstream_http_error


def test_map_connect_error_to_503():
    exc = httpx.ConnectError("connect failed")
    err = map_upstream_http_error("engine", exc)
    assert err.status_code == 503
    assert err.detail["service"] == "engine"
    assert err.detail["reason"] == "connect_error"


def test_map_read_timeout_to_504():
    exc = httpx.ReadTimeout("read timeout")
    err = map_upstream_http_error("trade", exc)
    assert err.status_code == 504
    assert err.detail["service"] == "trade"
    assert err.detail["reason"] == "read_timeout"


def test_map_other_http_error_to_502():
    exc = httpx.RemoteProtocolError("broken protocol")
    err = map_upstream_http_error("ai_ide", exc)
    assert err.status_code == 502
    assert err.detail["service"] == "ai_ide"
    assert err.detail["reason"] == "upstream_error"
