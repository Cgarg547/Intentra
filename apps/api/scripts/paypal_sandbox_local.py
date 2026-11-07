"""Configure and launch the local PayPal Sandbox API without echoing secrets."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import httpx
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from intentra.database import get_database_url
from intentra.services.merchant_registry import (
    MerchantRegistryError,
    TrustedMerchantRegistry,
)
from intentra.services.paypal_sandbox import (
    SANDBOX_BASE_URL,
    PayPalSandboxClient,
    PayPalSandboxConfig,
)
from intentra.schema_head import CURRENT_ALEMBIC_HEAD, has_current_schema_head


CONFIG_PATH = API_ROOT / ".env.paypal.sandbox.json"
FRONTEND_URL = "http://localhost:3000"
ALLOWED_ORIGINS = "http://localhost:3000"
FRONTEND_API_URL = "http://127.0.0.1:8000"
TARGET_REVISION = CURRENT_ALEMBIC_HEAD
PAYPAL_ACCOUNT_ID_PATTERN = re.compile(r"[2-9A-HJ-NP-Z]{13}\Z")
DISPOSABLE_SANDBOX_DATABASE_FLAG = "INTENTRA_ALLOW_DISPOSABLE_SANDBOX_DATABASE"
DISPOSABLE_SANDBOX_DATABASE = (
    "127.0.0.1",
    55433,
    "intentra_sandbox",
    "intentra_sandbox",
)


def _database_url_for_development() -> str:
    url = get_database_url()
    parsed = make_url(url)
    development_target = (
        parsed.host,
        parsed.port,
        parsed.database,
        parsed.username,
    )
    if development_target == ("127.0.0.1", 5433, "intentra", "intentra"):
        return url
    if (
        os.getenv(DISPOSABLE_SANDBOX_DATABASE_FLAG) == "1"
        and development_target == DISPOSABLE_SANDBOX_DATABASE
    ):
        return url
    raise RuntimeError(
        "Local setup requires the verified intentra development database, or the "
        "explicitly enabled disposable Sandbox database."
    )


async def _contract_merchants() -> list[str]:
    engine = create_async_engine(_database_url_for_development())
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                revisions = (
                    await connection.exec_driver_sql(
                        "SELECT version_num FROM alembic_version"
                    )
                ).scalars().all()
                if not has_current_schema_head(revisions):
                    raise RuntimeError("Development database revision is not current.")
                merchants = (
                    await connection.exec_driver_sql(
                        "SELECT DISTINCT merchant_id FROM intent_contracts ORDER BY merchant_id"
                    )
                ).scalars().all()
                return list(merchants)
    finally:
        await engine.dispose()


def _validate_config(config: object) -> dict:
    if not isinstance(config, dict):
        raise RuntimeError("Sandbox configuration is invalid.")
    client_id = config.get("PAYPAL_SANDBOX_CLIENT_ID")
    client_secret = config.get("PAYPAL_SANDBOX_CLIENT_SECRET")
    mappings = config.get("PAYPAL_SANDBOX_MERCHANTS")
    if not isinstance(client_id, str) or not client_id.strip():
        raise RuntimeError("Sandbox Client ID is missing.")
    if not isinstance(client_secret, str) or not client_secret.strip():
        raise RuntimeError("Sandbox Client Secret is missing.")
    try:
        registry = TrustedMerchantRegistry(mappings)
    except (MerchantRegistryError, TypeError, AttributeError) as exc:
        raise RuntimeError("Sandbox merchant registry is invalid.") from exc

    current_merchants = set(asyncio.run(_contract_merchants()))
    if set(mappings) != current_merchants:
        raise RuntimeError(
            "Registry keys must exactly match the development database contract merchant IDs."
        )
    for internal_id in current_merchants:
        merchant = registry.resolve(internal_id)
        if not PAYPAL_ACCOUNT_ID_PATTERN.fullmatch(merchant.paypal_merchant_id):
            raise RuntimeError(
                "PayPal merchant IDs must use the 13-character Sandbox account ID format."
            )

    if config.get("INTENTRA_FRONTEND_URL") != FRONTEND_URL:
        raise RuntimeError("Frontend origin must be http://localhost:3000.")
    if config.get("INTENTRA_ALLOWED_ORIGINS") != ALLOWED_ORIGINS:
        raise RuntimeError("Allowed origin must be http://localhost:3000.")
    if config.get("INTENTRA_API_URL") != FRONTEND_API_URL:
        raise RuntimeError("Frontend API URL must be http://127.0.0.1:8000.")
    return config


def _read_config() -> dict:
    try:
        info = CONFIG_PATH.lstat()
    except FileNotFoundError as exc:
        raise RuntimeError("Sandbox configuration is not installed yet.") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise RuntimeError("Sandbox configuration must be a regular local file.")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise RuntimeError("Sandbox configuration must be owned by the current user.")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise RuntimeError("Sandbox configuration permissions must be 0600.")
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Sandbox configuration could not be read.") from exc
    return _validate_config(data)


async def _authenticate(config: dict) -> None:
    http = httpx.AsyncClient(base_url=SANDBOX_BASE_URL)
    client = PayPalSandboxClient(
        PayPalSandboxConfig(
            config["PAYPAL_SANDBOX_CLIENT_ID"],
            config["PAYPAL_SANDBOX_CLIENT_SECRET"],
        ),
        http_client=http,
    )
    try:
        token = await client.get_access_token()
        # Deliberately never print, log, or persist the access token.
        del token
    finally:
        await http.aclose()


def _write_config(config: dict) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(CONFIG_PATH, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(config, stream, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(CONFIG_PATH, 0o600)
    except Exception:
        CONFIG_PATH.unlink(missing_ok=True)
        raise


def configure() -> None:
    if CONFIG_PATH.exists() or CONFIG_PATH.is_symlink():
        raise RuntimeError("Sandbox configuration already exists; refusing to overwrite it.")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError(
            "Run configure from an interactive terminal so credentials can be entered without echo."
        )
    merchants = asyncio.run(_contract_merchants())
    if not merchants:
        raise RuntimeError("No contract merchant IDs exist in the development database.")
    print("Enter credentials from the new INTENTRA Sandbox REST application only.")
    print("Do not use Default Application or legacy NVP/SOAP credentials.")
    client_id = getpass.getpass("New Sandbox REST Client ID (hidden): ")
    client_secret = getpass.getpass("New Sandbox REST Client Secret (hidden): ")
    mappings = {}
    for internal_id in merchants:
        print(f"Internal contract merchant ID: {internal_id}")
        paypal_id = getpass.getpass(
            "Verified Sandbox Business Account merchant ID (hidden): "
        )
        mappings[internal_id] = paypal_id
    config = {
        "PAYPAL_SANDBOX_CLIENT_ID": client_id,
        "PAYPAL_SANDBOX_CLIENT_SECRET": client_secret,
        "PAYPAL_SANDBOX_MERCHANTS": mappings,
        "INTENTRA_FRONTEND_URL": FRONTEND_URL,
        "INTENTRA_ALLOWED_ORIGINS": ALLOWED_ORIGINS,
        "INTENTRA_API_URL": FRONTEND_API_URL,
    }
    _validate_config(config)
    try:
        asyncio.run(_authenticate(config))
    except Exception as exc:
        raise RuntimeError(
            "PayPal Sandbox OAuth failed. Configuration was not saved; verify the new REST credentials."
        ) from exc
    _write_config(config)
    print("PayPal Sandbox OAuth: successful (token withheld).")
    print("Trusted merchant registry: valid for current contract merchant IDs.")
    print(f"Local configuration saved with mode 0600: {CONFIG_PATH}")
    print("No payment was created or submitted.")


def check() -> None:
    config = _read_config()
    try:
        asyncio.run(_authenticate(config))
    except Exception as exc:
        raise RuntimeError("PayPal Sandbox OAuth check failed; token withheld.") from exc
    print("PayPal Sandbox OAuth: successful (token withheld).")
    print("Trusted merchant registry: valid for current contract merchant IDs.")
    print("Origins: frontend=http://localhost:3000; API=http://127.0.0.1:8000.")
    print("No payment was created or submitted.")


def serve() -> None:
    config = _read_config()
    env = os.environ.copy()
    env.update(
        {
            "PAYPAL_SANDBOX_CLIENT_ID": config["PAYPAL_SANDBOX_CLIENT_ID"],
            "PAYPAL_SANDBOX_CLIENT_SECRET": config["PAYPAL_SANDBOX_CLIENT_SECRET"],
            "PAYPAL_SANDBOX_MERCHANTS": json.dumps(
                config["PAYPAL_SANDBOX_MERCHANTS"], separators=(",", ":")
            ),
            "INTENTRA_FRONTEND_URL": config["INTENTRA_FRONTEND_URL"],
            "INTENTRA_ALLOWED_ORIGINS": config["INTENTRA_ALLOWED_ORIGINS"],
        }
    )
    print("Starting only the INTENTRA API with local Sandbox configuration.")
    print("Stop the existing INTENTRA API first; this command does not kill processes.")
    command = [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"]
    result = subprocess.run(command, cwd=API_ROOT, env=env, check=False)
    raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("configure", "check", "serve"))
    action = parser.parse_args().action
    try:
        {"configure": configure, "check": check, "serve": serve}[action]()
    except (RuntimeError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
