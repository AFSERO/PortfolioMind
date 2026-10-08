"""Environment-aware security configuration tests."""

import secrets
import uuid

import pytest
from pydantic import ValidationError

from app.config import Settings


def _production_settings(**overrides) -> Settings:
    values = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": secrets.token_urlsafe(48),
        "DATABASE_URL": f"postgresql+asyncpg://security_test:{secrets.token_urlsafe(32)}@localhost/security_test",
        "INTEGRATION_TOKEN": None,
        "INTEGRATION_USER_ID": None,
        "PORTFOLIOMIND_API_TOKEN": None,
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": 15,
        "REFRESH_TOKEN_EXPIRE_DAYS": 7,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "secret",
    [
        "",
        "change-this-to-a-long-random-secret",
        "your-secret-key-change-this",
        "short",
        "a" * 64,
    ],
)
def test_production_rejects_missing_default_or_weak_secret(secret: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _production_settings(SECRET_KEY=secret)

    if secret:
        assert secret not in str(exc_info.value)


def test_explicit_test_secret_is_accepted() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="test",
        SECRET_KEY="test-only-secret-never-use-in-production",
        DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
    )

    assert settings.ENVIRONMENT == "test"


def test_staging_rejects_development_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="staging",
            SECRET_KEY="development-only-secret-never-use-in-production",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("JWT_ALGORITHM", "none"),
        ("ACCESS_TOKEN_EXPIRE_MINUTES", 0),
        ("REFRESH_TOKEN_EXPIRE_DAYS", -1),
    ],
)
def test_invalid_jwt_algorithm_or_expiration_is_rejected(field: str, value) -> None:
    with pytest.raises(ValidationError):
        _production_settings(**{field: value})


@pytest.mark.parametrize("environment", ["development", "staging", "production"])
def test_all_non_test_environments_reject_placeholder_credentials(environment):
    with pytest.raises(ValidationError):
        _production_settings(ENVIRONMENT=environment, SECRET_KEY="development-only-secret-never-use-in-production")
    with pytest.raises(ValidationError):
        _production_settings(ENVIRONMENT=environment, DATABASE_URL="postgresql+asyncpg://test:test@localhost/test")


def test_missing_credentials_fail_closed(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_database_credentials_are_redacted():
    password = secrets.token_urlsafe(32)
    configured = _production_settings(DATABASE_URL=f"postgresql+asyncpg://test:{password}@localhost/test")
    assert password not in repr(configured)
    with pytest.raises(ValidationError) as exc:
        _production_settings(DATABASE_URL=f"postgresql+asyncpg://test:{password}@localhost:invalid/test")
    assert password not in str(exc.value)


def test_integration_requires_strong_separate_token_and_explicit_owner():
    token = secrets.token_urlsafe(32)
    with pytest.raises(ValidationError):
        _production_settings(INTEGRATION_TOKEN=token)
    with pytest.raises(ValidationError):
        _production_settings(INTEGRATION_TOKEN="weak", INTEGRATION_USER_ID=uuid.uuid4())
    configured = _production_settings(INTEGRATION_TOKEN=token, INTEGRATION_USER_ID=uuid.uuid4())
    assert configured.integration_token == token
    assert token not in repr(configured)


def test_outbound_bridge_token_does_not_enable_inbound_auth():
    configured = _production_settings(PORTFOLIOMIND_API_TOKEN=secrets.token_urlsafe(32))
    assert configured.integration_token is None
