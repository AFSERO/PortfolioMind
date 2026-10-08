"""Initialize ignored local credentials without printing or overwriting secrets.

For FIRST-TIME setup only. Existing PostgreSQL volumes require a coordinated
role-password rotation; changing .env does not change an initialized database.
"""
import os
import re
import secrets
from pathlib import Path


def initialize(root: Path) -> None:
    destination = root / ".env"
    password = secrets.token_urlsafe(48)
    values = {
        "SECRET_KEY": secrets.token_urlsafe(48),
        "POSTGRES_PASSWORD": password,
        "DATABASE_URL": f"postgresql+asyncpg://networth:{password}@db:5432/networth",
    }
    template = (root / ".env.example").read_text(encoding="utf-8-sig")
    for key, value in values.items():
        template, replacements = re.subn(rf"^{key}=.*$", lambda _: f"{key}={value}", template, flags=re.M)
        if replacements != 1:
            raise RuntimeError("Invalid environment template")
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as env_file:
        env_file.write(template)
    print("Ignored .env initialized; credentials were not displayed. Finance bridge is disabled.")


if __name__ == "__main__":
    try:
        initialize(Path(__file__).resolve().parents[2])
    except FileExistsError:
        raise SystemExit("Existing .env was preserved. Use the coordinated rotation procedure.")
