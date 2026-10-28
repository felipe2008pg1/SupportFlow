import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base
from app.db.types import GUID


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    @validates("email")
    def _normalize_email(self, key: str, value: str) -> str:
        if not value or "@" not in value:
            raise ValueError("Invalid email address")
        normalized = value.strip().lower()
        if len(normalized) > 320:
            raise ValueError("Email address is too long")
        return normalized

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} is_active={self.is_active}>"