from functools import lru_cache
from typing import List

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables (and .env locally).

    Design decisions:
    - No default for `database_url`: a missing value must fail startup, not
      silently fall back to an insecure or wrong connection.
    - `extra="forbid"`: an unrecognized env var indicates a config typo/bug
      and should be caught immediately rather than ignored.
    - `debug=True` is rejected when `environment=production` (see validator
      below), preventing accidental production debug mode, which can leak
      stack traces and enable interactive debuggers (CWE-489).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        case_sensitive=False,
    )

    environment: str = Field(
        default="development",
        pattern="^(development|staging|production)$",
        description="Deployment environment. Controls docs exposure and debug validation.",
    )
    debug: bool = Field(default=False)

    # Comma-separated allowed origins for CORS. Empty by default: CORS is
    # opt-in and must be explicitly configured. A bare "*" is accepted as a
    # literal value here but the CORS middleware setup rejects combining it
    # with credentials, per OWASP CORS guidance.
    allowed_origins: str = Field(default="")

    database_url: str = Field(
        ...,
        description="PostgreSQL DSN, e.g. postgresql+psycopg://user:pass@host:5432/db",
    )

    # These three are never read by the application itself — they exist
    # solely so docker-compose's `db` service can pick them up via the same
    # .env file (the official postgres image requires them as env vars).
    # They are declared here anyway, with safe empty defaults, because this
    # Settings class also parses that same .env file locally (outside
    # Docker), and extra="forbid" would otherwise reject a correctly
    # filled-out .env for keys it doesn't recognize.
    postgres_user: str = Field(default="")
    postgres_password: str = Field(default="")
    postgres_db: str = Field(default="")

    @field_validator("debug")
    @classmethod
    def debug_disabled_in_production(cls, v: bool, info: ValidationInfo) -> bool:
        if info.data.get("environment") == "production" and v:
            raise ValueError("DEBUG must be False when ENVIRONMENT=production")
        return v

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Used as a FastAPI dependency later so
    settings are parsed once and can still be overridden in tests.
    """
    return Settings()
