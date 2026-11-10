import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Role
    is_active: bool
