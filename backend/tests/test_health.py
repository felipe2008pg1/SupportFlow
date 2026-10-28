from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_does_not_leak_internal_details() -> None:
    """Regression guard: health endpoint must never grow to expose
    version, hostname, DB status, or other internal details.
    """
    response = client.get("/health")
    assert set(response.json().keys()) == {"status"}


def test_docs_disabled_when_environment_is_production(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "false")

    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        from importlib import reload

        import app.main as main_module

        reload(main_module)

        assert main_module.app.docs_url is None
        assert main_module.app.redoc_url is None
        assert main_module.app.openapi_url is None
    finally:
        get_settings.cache_clear()
        reload(main_module)
