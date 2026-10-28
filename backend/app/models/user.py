import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base
from app.db.types import GUID


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    REQUESTER = "requester"
    TECHNICIAN = "technician"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=Role.REQUESTER,
        server_default=Role.REQUESTER.value,
    )
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
        role = self.role.value if self.role else None
        return f"<User id={self.id} email={self.email!r} role={role} is_active={self.is_active}>"