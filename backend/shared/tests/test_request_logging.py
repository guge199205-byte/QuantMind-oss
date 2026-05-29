from starlette.requests import Request

from backend.shared import request_logging


def _make_request(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/health",
            "raw_path": b"/health",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
    )


def test_extract_identity_from_headers():
    request = _make_request(
        [
            (b"x-tenant-id", b"tenant-a"),
            (b"x-user-id", b"user-1"),
        ]
    )
    tenant_id, user_id = request_logging.extract_identity_from_request(request)
    assert tenant_id == "tenant-a"
    assert user_id == "user-1"


def test_extract_identity_from_bearer_token(monkeypatch):
    request = _make_request([(b"authorization", b"Bearer mock-token")])

    def _mock_decode(_token: str):
        return {"tenant_id": "tenant-b", "sub": "2001"}

    monkeypatch.setattr(request_logging, "decode_jwt_token", _mock_decode)
    tenant_id, user_id = request_logging.extract_identity_from_request(request)
    assert tenant_id == "tenant-b"
    assert user_id == "2001"


def test_extract_identity_fallback_when_token_invalid(monkeypatch):
    request = _make_request([(b"authorization", b"Bearer bad-token")])

    def _mock_decode(_token: str):
        raise RuntimeError("decode failed")

    monkeypatch.setattr(request_logging, "decode_jwt_token", _mock_decode)
    tenant_id, user_id = request_logging.extract_identity_from_request(request)
    assert tenant_id == "default"
    assert user_id == "anonymous"
