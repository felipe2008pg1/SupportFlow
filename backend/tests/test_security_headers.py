from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_security_headers_present() -> None:
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["permissions-policy"]


def test_hsts_header_absent_over_plain_http() -> None:
    """HSTS is intentionally not set by the app itself; see middleware.py
    docstring. It must be added at the TLS termination point in production.
    """
    response = client.get("/health")
    assert "strict-transport-security" not in response.headers


def test_cors_allows_configured_frontend_origin() -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:8080"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8080"


def test_cors_rejects_unlisted_origin() -> None:
    response = client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_rejects_disallowed_method() -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "DELETE",
        },
    )
    assert response.headers.get("access-control-allow-methods") != "DELETE"
