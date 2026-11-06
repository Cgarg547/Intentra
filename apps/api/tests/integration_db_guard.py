"""Fail-closed configuration validation for database-writing integration tests.

This module deliberately uses only the standard library.  It must remain safe to
import before FastAPI, SQLAlchemy, or an application database engine is loaded.
"""
from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit


INTEGRATION_DATABASE_URL_ENV = "DATABASE_URL"
INTEGRATION_DATABASE_TARGET_ENV = "INTENTRA_TEST_DATABASE"
INTEGRATION_DATABASE_NAME = "intentra_ci_test"
INTEGRATION_DATABASE_USER = "intentra_ci_runner"
INTEGRATION_DATABASE_HOST = "127.0.0.1"
INTEGRATION_DATABASE_PORT = 5433
INTEGRATION_DATABASE_SCHEME = "postgresql+asyncpg"


class IntegrationDatabaseConfigurationError(ValueError):
    """Raised when an explicit integration database URL is not the CI target."""


def validate_integration_database_url(raw_url: str) -> str:
    """Return only the single approved CI PostgreSQL URL, otherwise fail closed."""
    if not isinstance(raw_url, str) or not raw_url:
        raise IntegrationDatabaseConfigurationError("Integration DATABASE_URL is required.")

    try:
        parsed = urlsplit(raw_url)
        port = parsed.port
        username = parsed.username
        hostname = parsed.hostname
    except ValueError as exc:
        raise IntegrationDatabaseConfigurationError(
            "Integration DATABASE_URL is malformed."
        ) from exc

    if (
        parsed.scheme != INTEGRATION_DATABASE_SCHEME
        or username != INTEGRATION_DATABASE_USER
        or hostname != INTEGRATION_DATABASE_HOST
        or port != INTEGRATION_DATABASE_PORT
        or parsed.path != f"/{INTEGRATION_DATABASE_NAME}"
        or not parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise IntegrationDatabaseConfigurationError(
            "Refusing integration tests outside the dedicated local CI database."
        )
    return raw_url


def configured_integration_database_url(environ: Mapping[str, str]) -> str | None:
    """Return ``None`` only when both explicit CI settings are absent.

    A partial configuration is unsafe: it could accidentally fall through to a
    developer setting or hide a typo in the disposable-target declaration.
    """
    raw_url = environ.get(INTEGRATION_DATABASE_URL_ENV)
    declared_target = environ.get(INTEGRATION_DATABASE_TARGET_ENV)
    if raw_url is None and declared_target is None:
        return None
    if raw_url is None or declared_target is None:
        raise IntegrationDatabaseConfigurationError(
            "DATABASE_URL and INTENTRA_TEST_DATABASE must be supplied together."
        )
    if declared_target != INTEGRATION_DATABASE_NAME:
        raise IntegrationDatabaseConfigurationError(
            "INTENTRA_TEST_DATABASE must name the dedicated CI database."
        )
    return validate_integration_database_url(raw_url)
