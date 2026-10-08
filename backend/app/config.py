import zoneinfo
from pathlib import Path
from typing import Literal
from uuid import UUID

from sqlalchemy.engine import make_url

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env files
_BACKEND_ENV = Path(__file__).parent.parent / ".env"
_ROOT_ENV = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_ENV), str(_BACKEND_ENV)),
        extra="ignore",
        hide_input_in_errors=True,
    )

    ENVIRONMENT: Literal["development", "test", "staging", "production"] = (
        "development"
    )
    # Database
    DATABASE_URL: str = Field(repr=False)

    # Secrets must be explicitly supplied, including in local development.
    SECRET_KEY: SecretStr
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, gt=0, le=1440)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, gt=0, le=365)

    # Cookies
    COOKIE_SECURE: bool = False  # Set True in production (HTTPS)

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True

    # CORS
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # Price APIs
    EXCHANGE_RATE_API_KEY: str = ""
    COINGECKO_BASE_URL: str = "https://api.coingecko.com/api/v3"
    METAL_PRICE_API_KEY: str = ""

    # Statement upload preflight (files are inspected in memory and not persisted)
    STATEMENT_PDF_MAX_BYTES: int = Field(
        default=10 * 1024 * 1024,
        gt=0,
        le=100 * 1024 * 1024,
    )

    # Local Integration (machine-to-machine sync for Investment Intelligence / Finance)
    INTEGRATION_TOKEN: SecretStr | None = None
    INTEGRATION_USER_ID: UUID | None = None
    PORTFOLIOMIND_API_TOKEN: SecretStr | None = None

    # Codex CLI AI Execution Timeouts
    CODEX_DEFAULT_TIMEOUT_SECONDS: float = Field(default=180.0, gt=0)
    CODEX_DEEP_RESEARCH_TIMEOUT_SECONDS: float = Field(default=600.0, gt=0)

    # Scheduled Daily Briefing Automation
    BRIEFING_SCHEDULER_ENABLED: bool = False
    BRIEFING_SCHEDULE_HOUR: int = Field(default=8, ge=0, le=23)
    BRIEFING_SCHEDULE_MINUTE: int = Field(default=0, ge=0, le=59)
    BRIEFING_SCHEDULE_TIMEZONE: str = "Europe/Istanbul"
    BRIEFING_SCHEDULE_CHECK_INTERVAL_SECONDS: int = Field(default=60, gt=0)

    @field_validator("BRIEFING_SCHEDULE_TIMEZONE")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            zoneinfo.ZoneInfo(v)
        except Exception as err:
            raise ValueError(
                f"Invalid timezone: '{v}'. Must be a valid IANA timezone string."
            ) from err
        return v

    @field_validator("INTEGRATION_USER_ID", mode="before")
    @classmethod
    def empty_integration_user_is_disabled(cls, value):
        return None if value == "" else value

    @property
    def jwt_secret(self) -> str:
        return self.SECRET_KEY.get_secret_value()

    @property
    def integration_token(self) -> str | None:
        if self.INTEGRATION_TOKEN:
            return self.INTEGRATION_TOKEN.get_secret_value() or None
        return None

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        secret = self.jwt_secret
        forbidden = {
            "change-this-to-a-long-random-secret",
            "development-only-secret-never-use-in-production",
            "your-secret-key-change-this",
            "your-secret-key",
            "ci-test-only-secret-never-use-in-production",
            "test-only-secret-never-use-in-production",
        }
        if self.ENVIRONMENT == "test":
            if len(secret) < 16:
                raise ValueError("JWT secret does not meet security requirements")
        elif len(secret) < 32 or len(set(secret)) < 8 or secret.strip().lower() in forbidden:
            raise ValueError("A strong, non-default JWT secret is required")

        try:
            database = make_url(self.DATABASE_URL)
            database.port  # Validate the port without including the URL in errors.
        except Exception:
            raise ValueError("Invalid database connection configuration") from None
        if self.ENVIRONMENT != "test":
            password = database.password or ""
            if (
                database.drivername != "postgresql+asyncpg"
                or not database.username or not database.database
                or len(password) < 32 or len(set(password)) < 8
                or password == database.username or password == secret
            ):
                raise ValueError("A PostgreSQL connection with a strong, separate password is required")

        token = self.integration_token
        if token is not None:
            if len(token) < 32 or len(set(token)) < 8 or token == secret or token == database.password:
                raise ValueError("A strong, separate integration credential is required")
            if self.INTEGRATION_USER_ID is None:
                raise ValueError("Integration authentication requires an explicit user UUID")
        return self


settings = Settings()
