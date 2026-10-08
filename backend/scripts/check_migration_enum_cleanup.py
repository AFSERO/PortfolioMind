"""Fail if a downgraded PostgreSQL schema still contains native ENUM types.

Run after downgrading below all revisions that own native ENUMs. This check
only reads the catalog; it never drops types or repairs the database.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        if engine.dialect.name != "postgresql":
            raise RuntimeError("ENUM cleanup verification requires PostgreSQL")
        async with engine.connect() as connection:
            enums = await connection.run_sync(
                lambda conn: inspect(conn).get_enums(schema="public")
            )
        remaining = sorted(enum["name"] for enum in enums)
        if remaining:
            raise RuntimeError(f"Downgrade left native ENUM types: {remaining}")
        print("PostgreSQL ENUM cleanup check passed")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
