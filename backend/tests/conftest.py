import os

# conftest.py is imported by pytest before test modules are collected, so
# these env vars are guaranteed to be set before `app.main` (and its
# lru_cache'd Settings) get imported anywhere in the test suite. This keeps
# Settings consistent across all test modules instead of depending on
# import order.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:8080")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db.base import Base  # noqa: E402
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