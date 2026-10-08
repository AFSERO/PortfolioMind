"""Integration tests create/drop only their own uniquely named database."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from investment_intelligence.database import create_db_engine


@pytest.fixture(scope="session")
def migration_config():
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


@pytest.fixture(scope="session")
def pg_engine(migration_config):
    raw_url = os.environ.get("II_TEST_ADMIN_URL")
    if not raw_url:
        pytest.fail("Set II_TEST_ADMIN_URL to a dedicated PostgreSQL test server (CREATEDB required).")
    url = make_url(raw_url)
    if url.drivername != "postgresql+psycopg":
        pytest.fail("II_TEST_ADMIN_URL must use postgresql+psycopg")
    # Never migrate/drop the database named in the supplied URL.
    name = "ii_test_" + uuid4().hex
    admin = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    # Exercise the real application engine settings, against our temporary database.
    with pytest.MonkeyPatch.context() as env:
        for key, value in {
            "II_DB_HOST": url.host or "127.0.0.1", "II_DB_PORT": str(url.port or 5432),
            "II_DB_NAME": name, "II_DB_USER": url.username, "II_DB_PASSWORD": url.password,
        }.items():
            env.setenv(key, value)
        engine = create_db_engine()
    created = False
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
            created = True
        with engine.begin() as connection:
            migration_config.attributes["connection"] = connection
            command.upgrade(migration_config, "head")
        migration_config.attributes.pop("connection", None)
        yield engine
    finally:
        migration_config.attributes.pop("connection", None)
        engine.dispose()
        if created:
            with admin.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE "{name}"')
        admin.dispose()


@pytest.fixture
def session(pg_engine):
    with pg_engine.connect() as connection:
        transaction = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


@pytest.fixture
def isolated_history_engine(pg_engine, migration_config):
    """Real commits without leaking undeletable history into other tests."""
    name = "ii_history_test_" + uuid4().hex
    admin = create_engine(pg_engine.url.set(database="postgres"),
                          isolation_level="AUTOCOMMIT", hide_parameters=True)
    engine = create_engine(pg_engine.url.set(database=name), hide_parameters=True,
                           connect_args={"options": "-c timezone=UTC"})
    created = False
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
            created = True
        with engine.begin() as connection:
            migration_config.attributes["connection"] = connection
            command.upgrade(migration_config, "head")
        migration_config.attributes.pop("connection", None)
        yield engine
    finally:
        migration_config.attributes.pop("connection", None)
        engine.dispose()
        try:
            if created:
                with admin.connect() as connection:
                    connection.exec_driver_sql(f'DROP DATABASE "{name}"')
        finally:
            admin.dispose()
