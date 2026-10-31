import asyncio
import os
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    env_file = Path(__file__).resolve().parents[2] / ".env"

    password = None
    for line in env_file.read_text().splitlines():
        if line.startswith("POSTGRES_PASSWORD="):
            password = line.split("=", 1)[1]
            break

    if not password:
        raise RuntimeError("POSTGRES_PASSWORD not found")

    database_url = (
        "postgresql+asyncpg://intentra:"
        f"{quote(password, safe='')}@127.0.0.1:5433/intentra"
    )

    engine = create_async_engine(database_url)

    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT current_database(), current_user, version()")
            )
            database, user, version = result.one()

            print("DATABASE CONNECTION SUCCESSFUL")
            print(f"Database: {database}")
            print(f"User: {user}")
            print(f"PostgreSQL: {version.split(',')[0]}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
