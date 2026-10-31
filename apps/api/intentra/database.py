import os
from pathlib import Path
from urllib.parse import quote

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url

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
