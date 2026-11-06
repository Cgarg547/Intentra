"""Explicit local operator command for the one verified legacy Sandbox order.

This script has no API route and refuses to run without an explicit
development-recovery confirmation flag. It only GETs PayPal order details.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import stat
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

API_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from intentra.services.merchant_registry import MerchantRegistryError, TrustedMerchantRegistry  # noqa: E402
from intentra.services.paypal_sandbox import PayPalSandboxClient, PayPalSandboxConfig  # noqa: E402
from intentra.services.payment_order_recovery import recover_existing_paypal_order  # noqa: E402
from intentra.schema_head import CURRENT_ALEMBIC_HEAD, has_current_schema_head  # noqa: E402


ATTEMPT_ID = "b2d84ff1-1905-4c09-9d43-9280e5d89e33"
RESERVATION_ID = "4c83cc56-7b8d-4851-9d99-b6a72ca74680"
CONTRACT_ID = "daaf9bed-903b-4736-9765-a67ede53820c"
ORDER_ID = "23X93125BY7169413"
INTERNAL_MERCHANT_ID = "paypal_merchant_demo"
TARGET_REVISION = CURRENT_ALEMBIC_HEAD
CONFIG_PATH = API_ROOT / ".env.paypal.sandbox.json"


def _database_url() -> URL:
    env_path = REPOSITORY_ROOT / ".env"
    password = None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("POSTGRES_PASSWORD="):
            password = line.split("=", 1)[1]
            break
    if not password:
        raise RuntimeError("Development database configuration is unavailable.")
    return URL.create(
        "postgresql+asyncpg", username="intentra", password=password,
        host="127.0.0.1", port=5433, database="intentra",
    )


def _read_provider_config() -> dict:
    try:
        info = CONFIG_PATH.lstat()
    except OSError:
        raise RuntimeError("Sandbox configuration is unavailable.") from None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise RuntimeError("Sandbox configuration must be a regular file.")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise RuntimeError("Sandbox configuration owner is invalid.")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise RuntimeError("Sandbox configuration permissions must be 0600.")
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise RuntimeError("Sandbox configuration is unavailable.") from None
    if not isinstance(config, dict):
        raise RuntimeError("Sandbox configuration is invalid.")
    return config


def _trusted_recovery_registry(config: dict) -> TrustedMerchantRegistry:
    """Load the recovery merchant mapping only from the private local config."""
    try:
        registry = TrustedMerchantRegistry(config.get("PAYPAL_SANDBOX_MERCHANTS"))
        registry.resolve(INTERNAL_MERCHANT_ID)
    except (MerchantRegistryError, TypeError, AttributeError):
        raise RuntimeError("Trusted Sandbox merchant mapping for recovery is unavailable.") from None
    return registry


async def _run() -> None:
    url = _database_url()
    parsed = make_url(url)
    if (parsed.host, parsed.port, parsed.database, parsed.username) != (
        "127.0.0.1", 5433, "intentra", "intentra",
    ):
        raise RuntimeError("Refusing an unexpected database target.")

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                identity = (await connection.execute(text(
                    "SELECT current_database(), current_user, inet_server_port()"
                ))).one()
                revisions = (await connection.execute(text(
                    "SELECT version_num FROM alembic_version"
                ))).scalars().all()
                if (identity[0] != "intentra" or identity[1] != "intentra"
                        or not has_current_schema_head(revisions)):
                    raise RuntimeError("Development database identity or revision changed.")

        config = _read_provider_config()
        registry = _trusted_recovery_registry(config)
        client_id = config.get("PAYPAL_SANDBOX_CLIENT_ID")
        client_secret = config.get("PAYPAL_SANDBOX_CLIENT_SECRET")
        if not isinstance(client_id, str) or not isinstance(client_secret, str):
            raise RuntimeError("Sandbox REST credentials are unavailable.")

        http = httpx.AsyncClient(base_url="https://api-m.sandbox.paypal.com")
        try:
            paypal = PayPalSandboxClient(
                PayPalSandboxConfig(client_id, client_secret), http_client=http,
            )
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                result = await recover_existing_paypal_order(
                    session,
                    attempt_id=uuid.UUID(ATTEMPT_ID),
                    expected_reservation_id=uuid.UUID(RESERVATION_ID),
                    expected_contract_id=uuid.UUID(CONTRACT_ID),
                    expected_contract_version=2,
                    provider_order_id=ORDER_ID,
                    dashboard_correlation_attempt_id=uuid.UUID(ATTEMPT_ID),
                    expected_internal_merchant_id=INTERNAL_MERCHANT_ID,
                    expected_amount=Decimal("1.00"),
                    expected_currency="USD",
                    registry=registry,
                    paypal=paypal,
                )
        finally:
            await http.aclose()
        print(f"Recovery result: {'bound' if result.changed else 'already bound'}.")
        print(f"Attempt: {result.attempt_id}; provider order: {result.provider_order_id}.")
        print("No order was created, no buyer approval was initiated, and no capture was submitted.")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-development-recovery", action="store_true", required=True,
        help="Explicitly authorize binding the verified order in the development database.",
    )
    parser.parse_args()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
