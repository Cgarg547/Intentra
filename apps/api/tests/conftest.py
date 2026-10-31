import os

import pytest
from sqlalchemy.engine import make_url


@pytest.fixture(autouse=True)
def isolate_integration_database_pool(request, monkeypatch):
    if request.module.__name__ != "tests.test_contract_integration" and (
        request.node.path.name != "test_contract_integration.py"
    ):
        yield
        return

    raw_url = os.getenv("DATABASE_URL")

    assert raw_url, "Integration tests require DATABASE_URL"

    url = make_url(raw_url)

    assert url.database == "intentra_test"
    assert url.host == "127.0.0.1"
    assert url.port == 5433

    yield
