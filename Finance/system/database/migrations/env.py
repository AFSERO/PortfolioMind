"""Use the same environment-only connection configuration as the application."""

from alembic import context

from investment_intelligence.database import Base, create_db_engine, database_url
from investment_intelligence import models  # noqa: F401: register model metadata


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=database_url(), target_metadata=Base.metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied_connection = context.config.attributes.get("connection")
    if supplied_connection is not None:
        run(supplied_connection)
    else:
        engine = create_db_engine()
        try:
            with engine.connect() as connection:
                run(connection)
        finally:
            engine.dispose()
