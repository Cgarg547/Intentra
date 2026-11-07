from sqlalchemy.engine import make_url

from intentra.database import normalize_database_url


def _assert_asyncpg_url(raw_url: str, expected_query: dict[str, str]) -> None:
    normalized = make_url(normalize_database_url(raw_url))

    assert normalized.drivername == "postgresql+asyncpg"
    assert normalized.username == "intentra"
    assert normalized.password == "synthetic-password"
    assert normalized.host == "db.example.test"
    assert normalized.port == 5432
    assert normalized.database == "intentra_preview"
    assert dict(normalized.query) == expected_query


def test_normalizes_postgres_scheme_without_losing_connection_components():
    _assert_asyncpg_url(
        "postgres://intentra:synthetic-password@db.example.test:5432/"
        "intentra_preview?application_name=intentra",
        {"application_name": "intentra"},
    )


def test_normalizes_postgresql_scheme_and_neon_ssl_parameters():
    _assert_asyncpg_url(
        "postgresql://intentra:synthetic-password@db.example.test:5432/"
        "intentra_preview?sslmode=require&channel_binding=require&application_name=intentra",
        {"ssl": "require", "application_name": "intentra"},
    )


def test_normalizes_psycopg_scheme_to_asyncpg():
    _assert_asyncpg_url(
        "postgresql+psycopg://intentra:synthetic-password@db.example.test:5432/"
        "intentra_preview?connect_timeout=10",
        {"connect_timeout": "10"},
    )


def test_leaves_asyncpg_scheme_and_ssl_parameter_intact():
    _assert_asyncpg_url(
        "postgresql+asyncpg://intentra:synthetic-password@db.example.test:5432/"
        "intentra_preview?ssl=require&application_name=intentra",
        {"ssl": "require", "application_name": "intentra"},
    )
