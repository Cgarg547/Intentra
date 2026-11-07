import os
from pathlib import Path
from urllib.parse import quote

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def normalize_database_url(raw_url: str) -> str:
    """Return a PostgreSQL URL that SQLAlchemy can use with asyncpg.

    Managed PostgreSQL providers commonly supply a libpq URL (or a psycopg
    URL).  This application uses SQLAlchemy's asyncpg dialect exclusively, so
    normalize those URLs before an async engine is constructed.  ``sslmode``
    is a libpq query argument; asyncpg expects the same mode as ``ssl``.
    ``channel_binding`` is also libpq-specific and is not accepted by
    ``asyncpg.connect``.
    """
    url = make_url(raw_url)

    if url.drivername not in {
        "postgres",
        "postgresql",
        "postgresql+psycopg",
        "postgresql+asyncpg",
    }:
        return raw_url

    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    if sslmode is not None and "ssl" not in query:
        query["ssl"] = sslmode
    query.pop("channel_binding", None)

    return url.set(
        drivername="postgresql+asyncpg",
        query=query,
    ).render_as_string(hide_password=False)


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return normalize_database_url(url)

    env_file = Path(__file__).resolve().parents[3] / ".env"

    if not env_file.exists():
        raise RuntimeError("Database configuration not found")

    password = None

    for line in env_file.read_text().splitlines():
        if line.startswith("POSTGRES_PASSWORD="):
            password = line.split("=", 1)[1]
            break

    if not password:
        raise RuntimeError("POSTGRES_PASSWORD missing")

    return (
        "postgresql+asyncpg://intentra:"
        f"{quote(password, safe='')}@127.0.0.1:5433/intentra"
    )


engine = create_async_engine(
    get_database_url(),
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with SessionLocal() as session:
        yield session
