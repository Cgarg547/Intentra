import pytest

from tests.integration_db_guard import (
    IntegrationDatabaseConfigurationError,
    configured_integration_database_url,
    validate_integration_database_url,
)


APPROVED_URL = (
    "postgresql+asyncpg://intentra_ci_runner:placeholder@127.0.0.1:5433/"
    "intentra_ci_test"
)


def test_accepts_only_the_dedicated_ci_target():
    assert validate_integration_database_url(APPROVED_URL) == APPROVED_URL


def test_unset_database_url_preserves_the_integration_skip_path():
    assert configured_integration_database_url({}) is None


@pytest.mark.parametrize(
    "environ",
    [
        {"DATABASE_URL": APPROVED_URL},
        {"INTENTRA_TEST_DATABASE": "intentra_ci_test"},
        {"DATABASE_URL": "", "INTENTRA_TEST_DATABASE": "intentra_ci_test"},
        {"DATABASE_URL": APPROVED_URL, "INTENTRA_TEST_DATABASE": "intentra_test"},
    ],
)
def test_partial_or_mismatched_explicit_configuration_fails_closed(environ):
    with pytest.raises(IntegrationDatabaseConfigurationError):
        configured_integration_database_url(environ)


def test_explicit_disposable_ci_configuration_is_accepted():
    assert configured_integration_database_url({
        "DATABASE_URL": APPROVED_URL,
        "INTENTRA_TEST_DATABASE": "intentra_ci_test",
    }) == APPROVED_URL


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://intentra_ci_runner:placeholder@127.0.0.1:5433/intentra",
        "postgresql+asyncpg://intentra_ci_runner:placeholder@127.0.0.1:5433/intentra_sandbox_demo",
        "postgresql+asyncpg://intentra_ci_runner:placeholder@127.0.0.1:5433/intentra_test",
        "postgresql+asyncpg://intentra:placeholder@127.0.0.1:5433/intentra_ci_test",
        "postgresql+asyncpg://postgres:placeholder@127.0.0.1:5433/intentra_ci_test",
        "postgresql+asyncpg://root:placeholder@127.0.0.1:5433/intentra_ci_test",
        "postgresql+asyncpg://admin:placeholder@127.0.0.1:5433/intentra_ci_test",
        "postgresql://intentra_ci_runner:placeholder@127.0.0.1:5433/intentra_ci_test",
        "postgresql+psycopg://intentra_ci_runner:placeholder@127.0.0.1:5433/intentra_ci_test",
        "sqlite://intentra_ci_runner:placeholder@127.0.0.1:5433/intentra_ci_test",
        "postgresql+asyncpg://intentra_ci_runner:placeholder@localhost:5433/intentra_ci_test",
        "postgresql+asyncpg://intentra_ci_runner:placeholder@127.0.0.2:5433/intentra_ci_test",
        "postgresql+asyncpg://intentra_ci_runner:placeholder@[::1]:5433/intentra_ci_test",
        "postgresql+asyncpg://intentra_ci_runner:placeholder@127.0.0.1:5432/intentra_ci_test",
        "postgresql+asyncpg://intentra_ci_runner:placeholder@127.0.0.1:5434/intentra_ci_test",
        "postgresql+asyncpg://intentra_ci_runner:placeholder@127.0.0.1:5433/intentra_ci_test?sslmode=disable",
        "postgresql+asyncpg://intentra_ci_runner@127.0.0.1:5433/intentra_ci_test",
        "not a database URL",
    ],
)
def test_rejects_every_non_ci_target(url):
    with pytest.raises(IntegrationDatabaseConfigurationError):
        validate_integration_database_url(url)
