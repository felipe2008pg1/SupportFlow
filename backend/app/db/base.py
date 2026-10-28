from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. Alembic's env.py imports this (and every
    model module, so they register on Base.metadata) to support
    autogenerate.
    """