import os

# conftest.py is imported by pytest before test modules are collected, so
# these env vars are guaranteed to be set before `app.main` (and its
# lru_cache'd Settings) get imported anywhere in the test suite. This keeps
# Settings consistent across all test modules instead of depending on
# import order.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789-abcdefghijkl")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:8080")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.models.refresh_token import RefreshToken  # noqa: E402,F401
from app.models.user import User  # noqa: E402,F401


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, future=True)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()

@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool

    from app.core import ratelimit
    from app.db.session import get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    ratelimit.login_by_account.clear()
    ratelimit.login_by_ip.clear()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, base_url="http://localhost") as c:
        c.session_factory = Session
        yield c
    app.dependency_overrides.clear()
    engine.dispose()