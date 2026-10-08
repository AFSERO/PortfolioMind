"""Environment-only PostgreSQL configuration and SQLAlchemy connection setup."""

import os
from collections.abc import Mapping
from datetime import datetime, timezone

from sqlalchemy import URL, DateTime, Engine, create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Keep native timestamptz; validate and normalize Python values at binding."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ValueError("Timezone-aware datetime required; naive datetime is not accepted")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        return value.astimezone(timezone.utc) if value is not None else None


class Base(DeclarativeBase):
    pass


def database_url(environ: Mapping[str, str] | None = None) -> URL:
    env = os.environ if environ is None else environ
    required = ("II_DB_NAME", "II_DB_USER", "II_DB_PASSWORD")
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise ValueError("Missing database environment variables: " + ", ".join(missing))
    try:
        port = int(env.get("II_DB_PORT", "55432"))
    except ValueError:
        raise ValueError("II_DB_PORT must be an integer between 1 and 65535") from None
    if not 1 <= port <= 65535:
        raise ValueError("II_DB_PORT must be an integer between 1 and 65535")
    return URL.create(
        "postgresql+psycopg",
        username=env["II_DB_USER"],
        password=env["II_DB_PASSWORD"],
        host=env.get("II_DB_HOST", "127.0.0.1"),
        port=port,
        database=env["II_DB_NAME"],
    )


def create_db_engine() -> Engine:
    # No connection or environment access at import time; no SQL parameter logging.
    return create_engine(
        database_url(), pool_pre_ping=True, hide_parameters=True,
        connect_args={"options": "-c timezone=UTC"},
    )
