"""Unit tests for RequestIdMiddleware."""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("SERVICE_NAME", "test-service")
os.environ.setdefault("APP_ENV", "development")

from mona_os_logger.context import get_request_id, set_request_id
from mona_os_logger.middleware import REQUEST_ID_HEADER


def test_request_id_header_constant():
    assert REQUEST_ID_HEADER == "X-Request-ID"


try:
    from starlette.testclient import TestClient
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from mona_os_logger.middleware import RequestIdMiddleware

    def _make_app() -> Starlette:
        def homepage(request):
            return JSONResponse({"request_id": get_request_id()})

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(RequestIdMiddleware)
        return app

    client = TestClient(_make_app(), raise_server_exceptions=True)

    def test_generates_request_id_if_missing():
        resp = client.get("/")
        assert resp.status_code == 200
        assert REQUEST_ID_HEADER in resp.headers
        rid = resp.headers[REQUEST_ID_HEADER]
        assert len(rid) == 36  # UUID format

    def test_reuses_incoming_request_id():
        existing = "my-existing-id-abc"
        resp = client.get("/", headers={REQUEST_ID_HEADER: existing})
        assert resp.headers[REQUEST_ID_HEADER] == existing
        assert resp.json()["request_id"] == existing

    def test_request_id_in_response_header():
        resp = client.get("/")
        assert REQUEST_ID_HEADER in resp.headers

    def test_request_id_propagated_to_context():
        existing = "propagate-test-id"
        resp = client.get("/", headers={REQUEST_ID_HEADER: existing})
        assert resp.json()["request_id"] == existing

    def test_health_check_not_logged():
        app2 = Starlette(routes=[
            Route("/healthz/live", lambda r: JSONResponse({"status": "live"}))
        ])
        app2.add_middleware(RequestIdMiddleware)
        c2 = TestClient(app2)
        resp = c2.get("/healthz/live")
        assert resp.status_code == 200

    def test_different_requests_get_different_ids():
        resp1 = client.get("/")
        resp2 = client.get("/")
        assert resp1.headers[REQUEST_ID_HEADER] != resp2.headers[REQUEST_ID_HEADER]

    def test_crlf_injection_rejected():
        """CRLF injection attempt must not be echoed back."""
        malicious = "valid-id\r\nSet-Cookie: evil=value"
        resp = client.get("/", headers={REQUEST_ID_HEADER: malicious})
        returned_id = resp.headers[REQUEST_ID_HEADER]
        assert "\r" not in returned_id
        assert "\n" not in returned_id
        assert "evil" not in returned_id
        assert len(returned_id) == 36  # generated UUID instead

    def test_invalid_request_id_generates_new():
        """Non-UUID-safe request IDs are replaced with generated ones."""
        resp = client.get("/", headers={REQUEST_ID_HEADER: "<script>xss</script>"})
        returned_id = resp.headers[REQUEST_ID_HEADER]
        assert "<" not in returned_id
        assert len(returned_id) == 36

    def test_valid_uuid_request_id_accepted():
        import uuid
        valid = str(uuid.uuid4())
        resp = client.get("/", headers={REQUEST_ID_HEADER: valid})
        assert resp.headers[REQUEST_ID_HEADER] == valid

except ImportError:
    pass
